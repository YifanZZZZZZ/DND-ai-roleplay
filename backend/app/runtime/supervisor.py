from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.app.agents import CharacterAgent, DeepSeekCharacterAgent
from backend.app.agents.character_agent import CharacterAgentResult
from backend.app.core.config import Settings, get_settings
from backend.app.db.base import utc_now
from backend.app.db.engine import async_session_factory
from backend.app.db.models import (
    AgentRun,
    Campaign,
    CampaignMembership,
    Character,
    CharacterMemory,
    CharacterProfile,
    CharacterSheetVersion,
    GameSession,
    LlmInvocation,
    Message,
    MessageRecipient,
    SessionCharacterState,
    SessionRuntime,
    SessionSummary,
)
from backend.app.domain.enums import (
    AgentRunStatus,
    AgentRunStopReason,
    CampaignLifecycleStatus,
    LlmInvocationStatus,
    LlmPurpose,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
    SessionStatus,
)
from backend.app.events import get_session_event_hub
from backend.app.runtime.coordinator import Candidate, SpeakerCoordinator
from backend.app.runtime.message_validator import MessageValidator
from backend.app.services.message_projection import EffectiveMessageProjection

AgentFactory = Callable[[Settings], CharacterAgent]
logger = logging.getLogger(__name__)
MAX_ERROR_MESSAGE_LENGTH = 4000


@dataclass(frozen=True, slots=True)
class _ClaimedCandidate:
    character_id: str
    character_name: str
    invocation_id: str
    context: str
    is_directly_addressed: bool
    last_spoken_sequence: int | None


@dataclass(frozen=True, slots=True)
class _ClaimedRun:
    run_id: str
    session_id: str
    generation: int
    candidates: tuple[_ClaimedCandidate, ...]


class RuntimeSupervisor:
    """Coordinates parallel character candidates and atomically publishes one."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] = async_session_factory,
        agent_factory: AgentFactory = DeepSeekCharacterAgent,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._agent_factory = agent_factory
        self._settings = settings or get_settings()
        self._coordinator = SpeakerCoordinator()
        self._validator = MessageValidator()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task is not None and not task.done():
            return
        task = asyncio.create_task(self._execute(run_id), name=f"character-agent:{run_id}")
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))

    async def recover_interrupted_runs(self) -> None:
        """Never replay an unknown in-flight provider request after restart."""
        async with self._session_factory() as session:
            runs = list(
                await session.scalars(
                    select(AgentRun).where(
                        AgentRun.status.in_([AgentRunStatus.PENDING, AgentRunStatus.RUNNING])
                    )
                )
            )
            for run in runs:
                run.status = AgentRunStatus.CANCELLED
                run.stop_reason = AgentRunStopReason.STALE
                run.finished_at = utc_now()
                game_session = await session.scalar(
                    select(GameSession)
                    .where(GameSession.id == run.session_id)
                    .options(selectinload(GameSession.runtime))
                )
                if game_session is not None and game_session.runtime.active_agent_run_id == run.id:
                    game_session.runtime.active_agent_run_id = None
                    game_session.runtime.status = RuntimeStatus.IDLE
            if runs:
                await session.commit()

    async def _execute(self, run_id: str) -> None:
        try:
            claimed = await self._claim(run_id)
            if claimed is None:
                return
            started_at = time.monotonic()
            try:
                agent = self._agent_factory(self._settings)
            except Exception as error:
                logger.exception(
                    "Character Agent initialization failed: run_id=%s session_id=%s",
                    run_id,
                    claimed.session_id,
                )
                results: list[CharacterAgentResult | BaseException] = [error] * len(
                    claimed.candidates
                )
            else:
                limiter = asyncio.Semaphore(self._settings.max_parallel_llm_calls)

                async def respond(candidate: _ClaimedCandidate) -> CharacterAgentResult:
                    async with limiter:
                        return await agent.respond(candidate.context)

                results = list(
                    await asyncio.gather(
                        *(respond(candidate) for candidate in claimed.candidates),
                        return_exceptions=True,
                    )
                )
            next_run_id = await self._commit_results(claimed, results, started_at)
            if next_run_id is not None:
                self.start(next_run_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Unhandled character runtime failure: run_id=%s", run_id)
            try:
                await self._record_unhandled_failure(run_id, error)
            except Exception:
                logger.exception(
                    "Failed to persist unhandled character runtime failure: run_id=%s",
                    run_id,
                )

    async def _claim(self, run_id: str) -> _ClaimedRun | None:
        async with self._session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None or run.status != AgentRunStatus.PENDING:
                return None
            game_session = await session.scalar(
                select(GameSession)
                .where(GameSession.id == run.session_id)
                .options(selectinload(GameSession.runtime), selectinload(GameSession.campaign))
            )
            if game_session is None or not self._run_is_current(run, game_session):
                self._mark_stale(run, game_session)
                await session.commit()
                return None
            trigger = await session.get(Message, run.trigger_message_id)
            if trigger is None:
                self._mark_stale(run, game_session)
                await session.commit()
                return None
            characters = list(
                await session.scalars(
                    select(Character)
                    .join(CampaignMembership, CampaignMembership.character_id == Character.id)
                    .join(
                        MessageRecipient,
                        MessageRecipient.character_id == CampaignMembership.character_id,
                    )
                    .where(
                        CampaignMembership.campaign_id == run.campaign_id,
                        MessageRecipient.message_id == run.trigger_message_id,
                        *(
                            [Character.id == run.selected_character_id]
                            if run.replacement_for_message_id is not None
                            and run.selected_character_id is not None
                            else []
                        ),
                    )
                    .order_by(CampaignMembership.joined_at, Character.id)
                )
            )
            if not characters:
                self._finish_silently(run, game_session)
                await session.commit()
                return None
            last_spoken_rows = await session.execute(
                select(Message.sender_character_id, func.max(Message.sequence_no))
                .where(
                    Message.session_id == run.session_id,
                    Message.sender_type == MessageSenderType.CHARACTER,
                    Message.kind != MessageKind.OOC,
                    Message.invalidated_at.is_(None),
                )
                .group_by(Message.sender_character_id)
            )
            last_spoken = {
                character_id: sequence
                for character_id, sequence in last_spoken_rows
                if character_id is not None
            }
            run.status = AgentRunStatus.RUNNING
            game_session.runtime.last_error_code = None
            game_session.runtime.last_error_message = None
            run.random_seed = (
                run.random_seed if run.random_seed is not None else secrets.randbits(63)
            )
            claims: list[_ClaimedCandidate] = []
            for character in characters:
                invocation = LlmInvocation(
                    campaign_id=run.campaign_id,
                    session_id=run.session_id,
                    agent_run_id=run.id,
                    character_id=character.id,
                    purpose=LlmPurpose.CHARACTER,
                    provider=self._settings.llm_provider,
                    model=self._settings.character_model,
                    status=LlmInvocationStatus.RUNNING,
                )
                session.add(invocation)
                await session.flush()
                context = await self._build_context(session, run, character)
                claims.append(
                    _ClaimedCandidate(
                        character_id=character.id,
                        character_name=character.name,
                        invocation_id=invocation.id,
                        context=context,
                        is_directly_addressed=(
                            character.name.casefold() in trigger.content.casefold()
                        ),
                        last_spoken_sequence=last_spoken.get(character.id),
                    )
                )
            await session.commit()
            return _ClaimedRun(
                run_id=run.id,
                session_id=run.session_id,
                generation=run.generation,
                candidates=tuple(claims),
            )

    async def _build_context(
        self, session: AsyncSession, run: AgentRun, character: Character
    ) -> str:
        sheet = None
        if character.active_sheet_version_id is not None:
            sheet = await session.scalar(
                select(CharacterSheetVersion).where(
                    CharacterSheetVersion.id == character.active_sheet_version_id,
                    CharacterSheetVersion.character_id == character.id,
                )
            )
        profile = await session.get(CharacterProfile, character.id)
        memories = list(
            await session.scalars(
                select(CharacterMemory)
                .where(CharacterMemory.character_id == character.id)
                .order_by(CharacterMemory.pinned.desc(), CharacterMemory.updated_at.desc())
                .limit(20)
            )
        )
        prior_summaries = list(
            await session.scalars(
                select(SessionSummary)
                .join(GameSession)
                .where(
                    SessionSummary.character_id == character.id,
                    GameSession.campaign_id == run.campaign_id,
                    GameSession.status == SessionStatus.ENDED,
                )
                .order_by(SessionSummary.updated_at.desc())
                .limit(5)
            )
        )
        states = list(
            await session.scalars(
                select(SessionCharacterState)
                .where(SessionCharacterState.session_id == run.session_id)
                .options(selectinload(SessionCharacterState.character))
                .order_by(SessionCharacterState.character_id)
            )
        )
        visible_messages = await session.scalars(
            EffectiveMessageProjection.for_session(run.session_id, character.id)
            .order_by(None)
            .order_by(Message.sequence_no.desc())
            .limit(40)
        )
        visible_messages = list(visible_messages)
        visible_messages.reverse()
        trigger = await session.get(Message, run.trigger_message_id)
        payload = {
            "角色身份与能力": sheet.parsed_snapshot if sheet is not None else {},
            "角色扮演指引": character.roleplay_prompt,
            "角色成长档案": profile.content if profile is not None else "",
            "角色长期记忆": [memory.content for memory in memories],
            "此前 Session 的角色可知记录": [item.content for item in prior_summaries],
            "小队可观察健康状态": [
                {
                    "name": state.character.name,
                    "health": self._health_label(state.current_hp, state.max_hp_snapshot),
                }
                for state in states
            ],
            "角色可见的近期消息": [
                {
                    "speaker": message.sender_character.name
                    if message.sender_character is not None
                    else "DM",
                    "kind": message.kind.value,
                    "content": message.content,
                }
                for message in visible_messages
            ],
        }
        if trigger is not None and trigger.kind == MessageKind.OOC:
            payload["OOC 纠正指令"] = trigger.content
        return json.dumps(payload, ensure_ascii=False, indent=2)

    async def _commit_results(
        self,
        claimed: _ClaimedRun,
        results: list[CharacterAgentResult | BaseException],
        started_at: float,
    ) -> str | None:
        async with self._session_factory() as session:
            run = await session.get(AgentRun, claimed.run_id)
            game_session = await session.scalar(
                select(GameSession)
                .where(GameSession.id == claimed.session_id)
                .options(
                    selectinload(GameSession.runtime),
                    selectinload(GameSession.campaign).selectinload(Campaign.memberships),
                )
            )
            if run is None:
                return None
            invocations = {
                invocation.id: invocation
                for invocation in list(
                    await session.scalars(
                        select(LlmInvocation).where(LlmInvocation.agent_run_id == run.id)
                    )
                )
            }
            elapsed_ms = self._elapsed_ms(started_at)
            if game_session is None or not self._run_is_current(run, game_session):
                for invocation in invocations.values():
                    if invocation.status == LlmInvocationStatus.RUNNING:
                        invocation.status = LlmInvocationStatus.CANCELLED
                        invocation.duration_ms = elapsed_ms
                        invocation.finished_at = utc_now()
                self._mark_stale(run, game_session)
                await session.commit()
                return None

            candidates: list[Candidate] = []
            successful_calls = 0
            failed_calls: list[str] = []
            for candidate, result in zip(claimed.candidates, results, strict=True):
                invocation = invocations[candidate.invocation_id]
                invocation.duration_ms = elapsed_ms
                invocation.finished_at = utc_now()
                if isinstance(result, BaseException):
                    error_message = self._exception_message(result)
                    invocation.status = LlmInvocationStatus.FAILED
                    invocation.error_code = "CHARACTER_AGENT_FAILED"
                    invocation.error_message = error_message
                    failed_calls.append(f"{candidate.character_name}: {error_message}")
                    logger.error(
                        "Character Agent call failed: run_id=%s session_id=%s "
                        "character_id=%s character_name=%s error=%s",
                        run.id,
                        claimed.session_id,
                        candidate.character_id,
                        candidate.character_name,
                        error_message,
                        exc_info=(type(result), result, result.__traceback__),
                    )
                    continue
                successful_calls += 1
                invocation.status = LlmInvocationStatus.COMPLETED
                invocation.input_tokens = result.input_tokens
                invocation.output_tokens = result.output_tokens
                candidates.append(
                    Candidate(
                        character_id=candidate.character_id,
                        character_name=candidate.character_name,
                        is_directly_addressed=candidate.is_directly_addressed,
                        last_spoken_sequence=candidate.last_spoken_sequence,
                        result=result,
                    )
                )
            if successful_calls == 0:
                error_message = self._truncate_error(
                    f"所有 {len(claimed.candidates)} 个角色调用均失败；" + "；".join(failed_calls)
                )
                logger.error(
                    "All Character Agent calls failed: run_id=%s session_id=%s details=%s",
                    run.id,
                    claimed.session_id,
                    error_message,
                )
                run.status = AgentRunStatus.FAILED
                run.stop_reason = AgentRunStopReason.ERROR
                run.finished_at = utc_now()
                game_session.runtime.active_agent_run_id = None
                game_session.runtime.status = RuntimeStatus.ERROR
                self._set_runtime_error(
                    game_session.runtime,
                    "ALL_CHARACTER_AGENTS_FAILED",
                    error_message,
                )
                await session.commit()
                await get_session_event_hub().publish("runtime.changed", claimed.session_id)
                return None

            selected = self._coordinator.select(candidates, run.random_seed or 0)
            if selected is None:
                self._finish_silently(run, game_session)
                await session.commit()
                await get_session_event_hub().publish("runtime.changed", claimed.session_id)
                return None

            decision = selected.result.decision
            if self._settings.enable_message_validator:
                game_session.runtime.status = RuntimeStatus.VALIDATING_MESSAGE
                validation = self._validator.validate(decision.content)
                if not validation.approved:
                    error_message = self._truncate_error(
                        f"角色“{selected.character_name}”的候选消息未通过校验："
                        f"{validation.reason or '未知原因'}"
                    )
                    logger.warning(
                        "Character message validation failed: run_id=%s session_id=%s "
                        "character_id=%s character_name=%s reason=%s content_length=%s",
                        run.id,
                        claimed.session_id,
                        selected.character_id,
                        selected.character_name,
                        validation.reason,
                        len(decision.content),
                    )
                    run.status = AgentRunStatus.FAILED
                    run.stop_reason = AgentRunStopReason.ERROR
                    run.finished_at = utc_now()
                    game_session.runtime.active_agent_run_id = None
                    game_session.runtime.status = RuntimeStatus.ERROR
                    self._set_runtime_error(
                        game_session.runtime,
                        "MESSAGE_VALIDATION_FAILED",
                        error_message,
                    )
                    await session.commit()
                    await get_session_event_hub().publish("runtime.changed", claimed.session_id)
                    return None
            run.selected_character_id = selected.character_id
            trigger = await session.get(Message, run.trigger_message_id)
            message = Message(
                session_id=game_session.id,
                sequence_no=game_session.next_sequence_no,
                sender_type=MessageSenderType.CHARACTER,
                sender_character_id=selected.character_id,
                kind=MessageKind.IN_GAME,
                audience=MessageAudience(decision.visibility),
                content=decision.content.strip(),
                origin_agent_run_id=run.id,
                supersedes_message_id=run.replacement_for_message_id,
                ooc_correction_note=(
                    trigger.content
                    if trigger is not None and trigger.kind == MessageKind.OOC
                    else None
                ),
            )
            recipient_ids = (
                [item.character_id for item in game_session.campaign.memberships]
                if decision.visibility == "PUBLIC"
                else [selected.character_id]
            )
            message.recipients = [
                MessageRecipient(character_id=character_id) for character_id in recipient_ids
            ]
            session.add(message)
            game_session.next_sequence_no += 1
            run.response_count += 1
            await session.flush()
            run.published_message_id = message.id
            run.status = AgentRunStatus.COMPLETED
            run.finished_at = utc_now()
            runtime = game_session.runtime
            runtime.active_agent_run_id = None
            runtime.consecutive_ai_messages += 1
            next_run_id: str | None = None
            if decision.requires_dm_resolution:
                run.stop_reason = AgentRunStopReason.WAITING_FOR_DM
                runtime.status = RuntimeStatus.WAITING_FOR_DM
                runtime.waiting_message_id = message.id
                runtime.waiting_request = (decision.resolution_request or "").strip()
            elif runtime.consecutive_ai_messages >= 12:
                run.stop_reason = AgentRunStopReason.LIMIT_REACHED
                runtime.status = RuntimeStatus.IDLE
            else:
                run.stop_reason = AgentRunStopReason.PUBLISHED
                followup = AgentRun(
                    campaign_id=run.campaign_id,
                    session_id=run.session_id,
                    trigger_message_id=message.id,
                    generation=runtime.generation,
                    status=AgentRunStatus.PENDING,
                    eligible_count=len(recipient_ids),
                    random_seed=secrets.randbits(63),
                )
                session.add(followup)
                await session.flush()
                runtime.active_agent_run_id = followup.id
                runtime.status = RuntimeStatus.AGENTS_EVALUATING
                next_run_id = followup.id
            await session.commit()
        await get_session_event_hub().publish("message.created", claimed.session_id)
        await get_session_event_hub().publish("runtime.changed", claimed.session_id)
        return next_run_id

    async def _record_unhandled_failure(self, run_id: str, error: BaseException) -> None:
        error_message = self._exception_message(error)
        async with self._session_factory() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                return
            game_session = await session.scalar(
                select(GameSession)
                .where(GameSession.id == run.session_id)
                .options(selectinload(GameSession.runtime))
            )
            invocations = list(
                await session.scalars(
                    select(LlmInvocation).where(
                        LlmInvocation.agent_run_id == run_id,
                        LlmInvocation.status == LlmInvocationStatus.RUNNING,
                    )
                )
            )
            for invocation in invocations:
                invocation.status = LlmInvocationStatus.FAILED
                invocation.error_code = "UNHANDLED_RUNTIME_ERROR"
                invocation.error_message = error_message
                invocation.finished_at = utc_now()
            if run.status in {AgentRunStatus.PENDING, AgentRunStatus.RUNNING}:
                run.status = AgentRunStatus.FAILED
                run.stop_reason = AgentRunStopReason.ERROR
                run.finished_at = utc_now()
            if game_session is not None and self._run_is_current(run, game_session):
                game_session.runtime.active_agent_run_id = None
                game_session.runtime.status = RuntimeStatus.ERROR
                self._set_runtime_error(
                    game_session.runtime,
                    "UNHANDLED_RUNTIME_ERROR",
                    error_message,
                )
            await session.commit()
        await get_session_event_hub().publish("runtime.changed", run.session_id)

    @staticmethod
    def _truncate_error(message: str) -> str:
        return message[:MAX_ERROR_MESSAGE_LENGTH]

    @classmethod
    def _exception_message(cls, error: BaseException) -> str:
        detail = str(error).strip() or "未提供异常详情"
        return cls._truncate_error(f"{type(error).__name__}: {detail}")

    @classmethod
    def _set_runtime_error(
        cls, runtime: SessionRuntime, error_code: str, error_message: str
    ) -> None:
        runtime.last_error_code = error_code
        runtime.last_error_message = cls._truncate_error(error_message)

    @staticmethod
    def _health_label(current_hp: int, max_hp: int) -> str:
        if current_hp <= 0:
            return "昏迷"
        ratio = current_hp / max_hp
        if ratio <= 0.25:
            return "濒危"
        if ratio <= 0.5:
            return "重伤"
        if ratio <= 0.75:
            return "轻伤"
        return "健康"

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(0, round((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _run_is_current(run: AgentRun, game_session: GameSession) -> bool:
        return (
            game_session.status == SessionStatus.ACTIVE
            and game_session.campaign.lifecycle_status == CampaignLifecycleStatus.ACTIVE
            and game_session.runtime.active_agent_run_id == run.id
            and game_session.runtime.generation == run.generation
        )

    @staticmethod
    def _mark_stale(run: AgentRun, game_session: GameSession | None) -> None:
        if run.status in {AgentRunStatus.PENDING, AgentRunStatus.RUNNING}:
            run.status = AgentRunStatus.CANCELLED
            run.stop_reason = AgentRunStopReason.STALE
            run.finished_at = utc_now()
        if game_session is not None and game_session.runtime.active_agent_run_id == run.id:
            game_session.runtime.active_agent_run_id = None
            game_session.runtime.status = RuntimeStatus.IDLE

    @staticmethod
    def _finish_silently(run: AgentRun, game_session: GameSession) -> None:
        run.status = AgentRunStatus.COMPLETED
        run.stop_reason = AgentRunStopReason.ALL_SILENT
        run.finished_at = utc_now()
        game_session.runtime.active_agent_run_id = None
        game_session.runtime.status = RuntimeStatus.IDLE
        game_session.runtime.waiting_message_id = None
        game_session.runtime.waiting_request = None


_runtime_supervisor = RuntimeSupervisor()


def get_runtime_supervisor() -> RuntimeSupervisor:
    return _runtime_supervisor
