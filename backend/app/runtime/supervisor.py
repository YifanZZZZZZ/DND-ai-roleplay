from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from backend.app.agents import CharacterAgent, DeepSeekCharacterAgent
from backend.app.agents.character_agent import CharacterAgentResult, CharacterDecision
from backend.app.agents.character_prompt import (
    RECENT_MESSAGE_LIMIT,
    CharacterContextInput,
    build_context,
    build_system_prompt,
    render_abilities,
)
from backend.app.core.config import Settings, get_settings
from backend.app.db.base import utc_now
from backend.app.db.engine import async_session_factory
from backend.app.db.models import (
    AgentRun,
    Campaign,
    CampaignMembership,
    Character,
    CharacterAcquaintance,
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
from backend.app.runtime.dm_draft_supervisor import DmDraftSupervisor
from backend.app.runtime.message_validator import MessageValidator
from backend.app.services.acquaintance_service import AcquaintanceService
from backend.app.services.message_projection import EffectiveMessageProjection
from backend.app.services.relationship_service import RelationshipService

AgentFactory = Callable[[Settings], CharacterAgent]
logger = logging.getLogger(__name__)
MAX_ERROR_MESSAGE_LENGTH = 4000
# Backstop for COMBAT play, where character replies do chain. Narrative play stops
# after every reply anyway, so this rarely bites there.
MAX_CONSECUTIVE_AI_MESSAGES = 5


@dataclass(frozen=True, slots=True)
class _ClaimedCandidate:
    character_id: str
    character_name: str
    invocation_id: str
    system_prompt: str
    context: str
    is_directly_addressed: bool
    last_spoken_sequence: int | None


@dataclass(frozen=True, slots=True)
class _ClaimedRun:
    run_id: str
    session_id: str
    generation: int
    random_seed: int
    candidates: tuple[_ClaimedCandidate, ...]


@dataclass(frozen=True, slots=True)
class _Selection:
    """The candidate that survived priority ordering and the publish gate."""

    character_id: str
    character_name: str
    decision: CharacterDecision


# Appended to the original context when a candidate fails the publish gate. The
# character keeps its own persona and history; only the offending line is retried.
_RETRY_NOTE = """<刚才那句被退回了>
你上一条回复没有通过发布前检查：{reason}
不要写任何数字或规则术语，也不要替 DM 宣布行动的成败——你只能描写"尝试"。
用同样的意思重写一条不违反边界的回复；如果实在没有合适的说法，就选 SILENCE。
</刚才那句被退回了>"""


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
        self._dm_draft_supervisor = DmDraftSupervisor(session_factory)
        self._enable_relationship_updates = agent_factory is DeepSeekCharacterAgent

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
            agent: CharacterAgent | None = None
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
                bound_agent = agent

                async def respond(candidate: _ClaimedCandidate) -> CharacterAgentResult:
                    async with limiter:
                        return await bound_agent.respond(
                            candidate.system_prompt, candidate.context
                        )

                results = list(
                    await asyncio.gather(
                        *(respond(candidate) for candidate in claimed.candidates),
                        return_exceptions=True,
                    )
                )
            selection, rejections = await self._select_publishable(agent, claimed, results)
            next_run_id = await self._commit_results(
                claimed, results, selection, rejections, started_at
            )
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
                        # Nobody answers their own line. Without this the speaker
                        # is re-triggered by their own message, and in a one-character
                        # campaign that is the only candidate — the character then
                        # holds both sides of the conversation until the cap.
                        *(
                            [Character.id != trigger.sender_character_id]
                            if trigger.sender_character_id is not None
                            else []
                        ),
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
            addressed_ids = self._resolve_addressed(trigger, characters)
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
                system_prompt, context = await self._build_prompts(session, run, character)
                claims.append(
                    _ClaimedCandidate(
                        character_id=character.id,
                        character_name=character.name,
                        invocation_id=invocation.id,
                        system_prompt=system_prompt,
                        context=context,
                        is_directly_addressed=character.id in addressed_ids,
                        last_spoken_sequence=last_spoken.get(character.id),
                    )
                )
            await session.commit()
            return _ClaimedRun(
                run_id=run.id,
                session_id=run.session_id,
                generation=run.generation,
                random_seed=run.random_seed,
                candidates=tuple(claims),
            )

    @staticmethod
    def _resolve_addressed(trigger: Message, characters: list[Character]) -> set[str]:
        """Explicit addressing first; name matching only as a fallback.

        Substring matching alone silently failed on pronouns ("你们两个先进去"),
        which collapsed the coordinator's first priority tier and made the party
        look like it was speaking in turn order.
        """
        explicit = {
            character.id
            for character in characters
            if character.id in set(trigger.addressed_character_ids or [])
        }
        if explicit:
            return explicit
        content = trigger.content.casefold()
        return {
            character.id for character in characters if character.name.casefold() in content
        }

    async def _build_prompts(
        self, session: AsyncSession, run: AgentRun, character: Character
    ) -> tuple[str, str]:
        """Identity goes to the system prompt, world state to the user message."""
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
                .order_by(
                    CharacterMemory.pinned.desc(),
                    # Pinned first, then this campaign, then the most recent.
                    case(
                        (CharacterMemory.source_campaign_id == run.campaign_id, 0),
                        else_=1,
                    ),
                    CharacterMemory.updated_at.desc(),
                )
                .limit(40)
            )
        )
        prior_summaries = list(
            await session.scalars(
                select(SessionSummary)
                .join(GameSession)
                .where(
                    SessionSummary.character_id == character.id,
                    GameSession.status == SessionStatus.ENDED,
                )
                .options(selectinload(SessionSummary.session))
                .order_by(GameSession.started_at.asc(), SessionSummary.created_at.asc())
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
        visible_messages = list(
            await session.scalars(
                EffectiveMessageProjection.for_session(run.session_id, character.id)
                .order_by(None)
                .order_by(Message.sequence_no.asc())
            )
        )
        trigger = await session.get(Message, run.trigger_message_id)
        acquainted_ids = await AcquaintanceService(session).acquainted_character_ids(character.id)
        relationship_rows = list(
            await session.scalars(
                select(CharacterAcquaintance).where(
                    (CharacterAcquaintance.character_a_id == character.id)
                    | (CharacterAcquaintance.character_b_id == character.id)
                )
            )
        )
        related_characters = {
            related.id: related
            for related_id in acquainted_ids
            if (related := await session.get(Character, related_id)) is not None
        }
        other_states = [state for state in states if state.character_id != character.id]
        stranger_aliases = {
            state.character_id: f"陌生人#{index}"
            for index, state in enumerate(other_states, start=1)
            if state.character_id not in acquainted_ids
        }

        def visible_name(other: Character) -> str:
            if other.id == character.id or other.id in acquainted_ids:
                return other.name
            return stranger_aliases.get(other.id, "陌生人")

        def redact_unknown_names(content: str) -> str:
            for state in sorted(
                other_states, key=lambda item: len(item.character.name), reverse=True
            ):
                alias = stranger_aliases.get(state.character_id)
                if alias is not None:
                    content = content.replace(state.character.name, alias)
            return content

        def speaker_of(message: Message) -> str:
            if message.sender_character is None:
                return "DM"
            return visible_name(message.sender_character)

        history = [
            message
            for message in visible_messages
            if trigger is None or message.id != trigger.id
        ][-RECENT_MESSAGE_LIMIT:]

        relationships = [
            (
                related_characters[related_id].name,
                relationship.relationship_history,
            )
            for relationship in relationship_rows
            if (
                related_id := (
                    relationship.character_b_id
                    if relationship.character_a_id == character.id
                    else relationship.character_a_id
                )
            )
            in related_characters
        ]
        for state in other_states:
            alias = stranger_aliases.get(state.character_id)
            if alias is not None:
                relationships.append((alias, "你还不认识这个人。"))

        is_ooc = trigger is not None and trigger.kind == MessageKind.OOC
        context = build_context(
            CharacterContextInput(
                abilities=render_abilities(sheet.parsed_snapshot if sheet is not None else None),
                memories=[memory.content for memory in memories],
                relationships=relationships,
                past_stories=[(item.session.title, item.content) for item in prior_summaries],
                health=[
                    (
                        "你自己" if state.character_id == character.id
                        else visible_name(state.character),
                        self._health_label(state.current_hp, state.max_hp_snapshot),
                    )
                    for state in states
                ],
                has_strangers=bool(stranger_aliases),
                recent_messages=[
                    (speaker_of(message), redact_unknown_names(message.content))
                    for message in history
                ],
                trigger_speaker=(
                    speaker_of(trigger) if trigger is not None and not is_ooc else None
                ),
                trigger_content=(
                    redact_unknown_names(trigger.content)
                    if trigger is not None and not is_ooc
                    else None
                ),
                ooc_correction=(
                    redact_unknown_names(trigger.content)
                    if trigger is not None and is_ooc
                    else None
                ),
            )
        )
        system_prompt = build_system_prompt(
            name=character.name,
            roleplay_prompt=character.roleplay_prompt,
            voice_samples=character.voice_samples,
            profile_content=profile.content if profile is not None else "",
            narration_notes=character.narration_notes,
        )
        return system_prompt, context

    async def _select_publishable(
        self,
        agent: CharacterAgent | None,
        claimed: _ClaimedRun,
        results: list[CharacterAgentResult | BaseException],
    ) -> tuple[_Selection | None, list[str]]:
        """Walk the priority order until one candidate clears the publish gate.

        A rejected line used to abort the whole run and park the campaign in
        ERROR. Now the author gets one corrective retry, and failing that the
        next-ranked character speaks instead — the table keeps moving.
        """
        candidates = [
            Candidate(
                character_id=claimed_candidate.character_id,
                character_name=claimed_candidate.character_name,
                is_directly_addressed=claimed_candidate.is_directly_addressed,
                last_spoken_sequence=claimed_candidate.last_spoken_sequence,
                result=result,
            )
            for claimed_candidate, result in zip(claimed.candidates, results, strict=True)
            if not isinstance(result, BaseException)
        ]
        if not candidates:
            return None, []

        ranked = self._coordinator.rank(candidates, claimed.random_seed)
        if not self._settings.enable_message_validator:
            if not ranked:
                return None, []
            best = ranked[0]
            return _Selection(best.character_id, best.character_name, best.result.decision), []

        sources = {item.character_id: item for item in claimed.candidates}
        rejections: list[str] = []
        for candidate in ranked:
            decision = candidate.result.decision
            validation = self._validator.validate(decision.content)
            if validation.approved:
                return (
                    _Selection(candidate.character_id, candidate.character_name, decision),
                    rejections,
                )
            reason = validation.reason or "未知原因"
            rejections.append(f"{candidate.character_name}：{reason}")
            logger.warning(
                "Character message rejected: run_id=%s session_id=%s character_id=%s "
                "character_name=%s reason=%s content_length=%s",
                claimed.run_id,
                claimed.session_id,
                candidate.character_id,
                candidate.character_name,
                reason,
                len(decision.content),
            )
            source = sources.get(candidate.character_id)
            if agent is None or source is None:
                continue
            try:
                retried = await agent.respond(
                    source.system_prompt,
                    f"{source.context}\n\n{_RETRY_NOTE.format(reason=reason)}",
                )
            except Exception:
                logger.exception(
                    "Character Agent retry failed: run_id=%s character_id=%s",
                    claimed.run_id,
                    candidate.character_id,
                )
                continue
            retried_decision = retried.decision
            if retried_decision.decision != "RESPOND":
                continue
            revalidation = self._validator.validate(retried_decision.content)
            if revalidation.approved:
                return (
                    _Selection(
                        candidate.character_id, candidate.character_name, retried_decision
                    ),
                    rejections,
                )
            rejections.append(
                f"{candidate.character_name}（重试）：{revalidation.reason or '未知原因'}"
            )
        return None, rejections

    async def _commit_results(
        self,
        claimed: _ClaimedRun,
        results: list[CharacterAgentResult | BaseException],
        selection: _Selection | None,
        rejections: list[str],
        started_at: float,
    ) -> str | None:
        async with self._session_factory() as session:
            run = await session.get(AgentRun, claimed.run_id)
            game_session = await session.scalar(
                select(GameSession)
                .where(GameSession.id == claimed.session_id)
                .options(
                    selectinload(GameSession.runtime),
                    selectinload(GameSession.campaign)
                    .selectinload(Campaign.memberships)
                    .selectinload(CampaignMembership.character),
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

            successful_calls = 0
            failed_calls: list[str] = []
            silent_draft_message_id: str | None = None
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

            if selection is None:
                self._finish_silently(run, game_session)
                # Nobody has anything left to say. If the round was triggered by a
                # character rather than the DM, the scene has stalled and the DM is
                # the one who has to move it, so draft something for them.
                trigger = await session.get(Message, run.trigger_message_id)
                if (
                    game_session.campaign.play_mode.value == "NARRATIVE"
                    and trigger is not None
                    and trigger.sender_type == MessageSenderType.CHARACTER
                ):
                    silent_draft_message_id = trigger.id
                if rejections:
                    # Nobody speaks this round, but the DM still needs to know the
                    # model kept getting blocked. Surfaced as a non-blocking banner
                    # rather than an ERROR that halts the campaign.
                    self._set_runtime_error(
                        game_session.runtime,
                        "CHARACTER_MESSAGE_REJECTED",
                        self._truncate_error(
                            "本轮所有角色候选都未通过发布前检查：" + "；".join(rejections)
                        ),
                    )
                await session.commit()
                await get_session_event_hub().publish("runtime.changed", claimed.session_id)
                if silent_draft_message_id is not None:
                    self._dm_draft_supervisor.start(
                        silent_draft_message_id, claimed.session_id
                    )
                return None

            decision = selection.decision
            if rejections:
                self._set_runtime_error(
                    game_session.runtime,
                    "CHARACTER_MESSAGE_REJECTED",
                    self._truncate_error("部分角色候选未通过发布前检查：" + "；".join(rejections)),
                )
            run.selected_character_id = selection.character_id
            trigger = await session.get(Message, run.trigger_message_id)
            peer_names = [
                item.character.name
                for item in game_session.campaign.memberships
                if item.character_id != selection.character_id
            ]
            forced_resolution = self._question_needs_the_world(
                decision.content, trigger, peer_names, decision.addressed_character_ids
            )
            message = Message(
                session_id=game_session.id,
                sequence_no=game_session.next_sequence_no,
                sender_type=MessageSenderType.CHARACTER,
                sender_character_id=selection.character_id,
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
                else [selection.character_id]
            )
            # Carried onto the message so the next run's coordinator can honour
            # "I'm talking to you two" without re-parsing the sentence.
            visible_ids = set(recipient_ids)
            message.addressed_character_ids = [
                character_id
                for character_id in dict.fromkeys(decision.addressed_character_ids)
                if character_id in visible_ids and character_id != selection.character_id
            ][:6]
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
            auto_dm_draft_message_id: str | None = None
            narrative = game_session.campaign.play_mode.value == "NARRATIVE"
            if decision.requires_dm_resolution or forced_resolution:
                # The character reached for something it cannot decide on its own:
                # an outcome, an NPC's reaction, a fact about the world. Only this
                # stops the table — pure inter-character talk keeps flowing.
                run.stop_reason = AgentRunStopReason.WAITING_FOR_DM
                runtime.status = RuntimeStatus.WAITING_FOR_DM
                runtime.waiting_message_id = message.id
                runtime.waiting_request = (
                    decision.resolution_request or ""
                ).strip() or "角色向场景中的人或物提出了问题，等待 DM 给出回应。"
                if narrative:
                    auto_dm_draft_message_id = message.id
            elif runtime.consecutive_ai_messages >= MAX_CONSECUTIVE_AI_MESSAGES:
                run.stop_reason = AgentRunStopReason.LIMIT_REACHED
                runtime.status = RuntimeStatus.IDLE
                if narrative:
                    auto_dm_draft_message_id = message.id
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
        if self._enable_relationship_updates:
            async with self._session_factory() as relationship_session:
                await RelationshipService(
                    relationship_session, self._settings
                ).refresh_for_campaign(run.campaign_id)
        await get_session_event_hub().publish("message.created", claimed.session_id)
        await get_session_event_hub().publish("runtime.changed", claimed.session_id)
        if auto_dm_draft_message_id is not None:
            self._dm_draft_supervisor.start(auto_dm_draft_message_id, claimed.session_id)
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
    def _question_needs_the_world(
        content: str,
        trigger: Message | None,
        peer_names: list[str],
        addressed_character_ids: list[str],
    ) -> bool:
        """Backstop for a character that asks the world something without saying so.

        The model is supposed to raise ``requires_dm_resolution`` itself, but when
        it forgets, the next character run has an unanswered question sitting in
        the log and fills it in — inventing the NPC's reply. Over-waiting costs a
        draft the DM can ignore; under-waiting lets the AI speak for the world.

        Only fires on a question raised in reaction to the DM, aimed at nobody in
        the party, so ordinary party discussion keeps flowing.
        """
        if not any(mark in content for mark in ("？", "?")):
            return False
        if addressed_character_ids:
            return False
        if trigger is None or trigger.sender_type != MessageSenderType.DM:
            return False
        return not any(name and name in content for name in peer_names)

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
