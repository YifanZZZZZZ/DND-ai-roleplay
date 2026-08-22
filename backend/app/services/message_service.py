from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.api.schemas.messages import DmMessageCreate, OocCorrectionCreate
from backend.app.core.config import get_settings
from backend.app.core.errors import AppError, ConflictError, NotFoundError
from backend.app.db.models import (
    AgentRun,
    Campaign,
    CampaignMembership,
    GameSession,
    Message,
    MessageRecipient,
    SessionRuntime,
)
from backend.app.domain.enums import (
    AgentRunStatus,
    AgentRunStopReason,
    CampaignLifecycleStatus,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    RuntimeStatus,
    SessionStatus,
)
from backend.app.services.message_projection import EffectiveMessageProjection


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _session_query(self):
        return select(GameSession).options(
            selectinload(GameSession.campaign)
            .selectinload(Campaign.memberships)
            .selectinload(CampaignMembership.character),
            selectinload(GameSession.runtime),
        )

    async def _get_session(self, session_id: str) -> GameSession:
        game_session = await self.session.scalar(
            self._session_query().where(GameSession.id == session_id)
        )
        if game_session is None:
            raise NotFoundError("Session", session_id)
        return game_session

    async def list(self, session_id: str) -> list[Message]:
        await self._get_session(session_id)
        return await EffectiveMessageProjection.session_messages(self.session, session_id)

    async def get(self, message_id: str) -> Message:
        message = await self.session.scalar(
            select(Message)
            .where(Message.id == message_id)
            .options(
                selectinload(Message.sender_character),
                selectinload(Message.recipients).selectinload(MessageRecipient.character),
            )
        )
        if message is None:
            raise NotFoundError("Message", message_id)
        return message

    async def send_dm_message(
        self, session_id: str, payload: DmMessageCreate
    ) -> tuple[Message, GameSession]:
        request_id = str(payload.client_request_id)
        existing = await self.session.scalar(
            select(Message).where(Message.client_request_id == request_id)
        )
        if existing is not None:
            if existing.session_id != session_id:
                raise ConflictError(
                    "CLIENT_REQUEST_ID_REUSED",
                    "这条客户端请求 ID 已用于其他 Session。",
                )
            return await self.get(existing.id), await self._get_session(session_id)

        game_session = await self._get_session(session_id)
        if game_session.status != SessionStatus.ACTIVE:
            raise ConflictError("SESSION_ENDED", "已结束的 Session 不能发送消息。")
        if game_session.campaign.lifecycle_status != CampaignLifecycleStatus.ACTIVE:
            raise ConflictError("CAMPAIGN_NOT_ACTIVE", "只有进行中的战役可以发送消息。")

        recipient_ids = self._resolve_recipient_ids(game_session, payload)
        runtime = game_session.runtime
        runtime.generation += 1
        await self._cancel_active_run(runtime, AgentRunStopReason.DM_PREEMPTED)

        message = Message(
            session=game_session,
            sequence_no=game_session.next_sequence_no,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.IN_GAME,
            audience=payload.audience,
            content=payload.content.strip(),
            client_request_id=request_id,
        )
        message.recipients = [
            MessageRecipient(character_id=character_id) for character_id in recipient_ids
        ]
        game_session.next_sequence_no += 1
        self.session.add(message)
        await self.session.flush()

        runtime.waiting_message_id = None
        runtime.waiting_request = None
        runtime.last_error_code = None
        runtime.last_error_message = None
        runtime.last_trigger_message_id = message.id
        runtime.consecutive_ai_messages = 0
        runtime.status = RuntimeStatus.AGENTS_EVALUATING

        run = AgentRun(
            campaign_id=game_session.campaign_id,
            session_id=game_session.id,
            trigger_message_id=message.id,
            generation=runtime.generation,
            status=AgentRunStatus.PENDING,
            eligible_count=len(recipient_ids),
            random_seed=secrets.randbits(63),
        )
        self.session.add(run)
        await self.session.flush()
        if get_settings().character_agent_is_configured:
            runtime.active_agent_run_id = run.id
        else:
            # Until a real model adapter is configured, preserve the full message
            # transaction and run audit trail without leaving the UI in a false
            # "generating" state.
            run.status = AgentRunStatus.COMPLETED
            run.stop_reason = AgentRunStopReason.ALL_SILENT
            run.finished_at = datetime.now(UTC)
            runtime.status = RuntimeStatus.IDLE
        await self.session.commit()
        return await self.get(message.id), await self._get_session(session_id)

    async def correct_with_ooc(self, session_id: str, payload: OocCorrectionCreate) -> GameSession:
        request_id = str(payload.client_request_id)
        existing = await self.session.scalar(
            select(Message).where(Message.client_request_id == request_id)
        )
        if existing is not None:
            if existing.session_id != session_id:
                raise ConflictError(
                    "CLIENT_REQUEST_ID_REUSED", "这条客户端请求 ID 已用于其他 Session。"
                )
            return await self._get_session(session_id)
        game_session = await self._get_session(session_id)
        if game_session.status != SessionStatus.ACTIVE:
            raise ConflictError("SESSION_ENDED", "已结束的 Session 不能发送 OOC 纠正。")
        target = await self.get(payload.target_message_id)
        if target.session_id != session_id or target.kind == MessageKind.OOC:
            raise AppError("INVALID_OOC_TARGET", "只能纠正当前 Session 的场内消息。")
        latest = await self.session.scalar(
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.kind != MessageKind.OOC,
                Message.invalidated_at.is_(None),
            )
            .order_by(Message.sequence_no.desc())
        )
        if latest is None or latest.id != target.id:
            raise ConflictError("OOC_TARGET_NOT_LATEST", "OOC 只能纠正最新的有效场内消息。")
        if (
            target.sender_type == MessageSenderType.DM
            and not (payload.replacement_content or "").strip()
        ):
            raise AppError("DM_REPLACEMENT_REQUIRED", "纠正 DM 消息时必须提供正确版本。")

        runtime = game_session.runtime
        runtime.generation += 1
        await self._cancel_active_run(runtime, AgentRunStopReason.DM_PREEMPTED)
        ooc = Message(
            session=game_session,
            sequence_no=game_session.next_sequence_no,
            sender_type=MessageSenderType.DM,
            kind=MessageKind.OOC,
            audience=target.audience,
            content=payload.correction.strip(),
            client_request_id=request_id,
        )
        ooc.recipients = [
            MessageRecipient(character_id=item.character_id) for item in target.recipients
        ]
        self.session.add(ooc)
        game_session.next_sequence_no += 1
        await self.session.flush()
        target.invalidated_at = datetime.now(UTC)
        target.invalidated_by_ooc_id = ooc.id
        runtime.waiting_message_id = None
        runtime.waiting_request = None
        runtime.last_error_code = None
        runtime.last_error_message = None
        runtime.consecutive_ai_messages = 0

        if target.sender_type == MessageSenderType.DM:
            replacement = Message(
                session=game_session,
                sequence_no=game_session.next_sequence_no,
                sender_type=MessageSenderType.DM,
                kind=MessageKind.IN_GAME,
                audience=target.audience,
                content=(payload.replacement_content or "").strip(),
                supersedes_message_id=target.id,
                ooc_correction_note=ooc.content,
            )
            replacement.recipients = [
                MessageRecipient(character_id=item.character_id) for item in target.recipients
            ]
            self.session.add(replacement)
            game_session.next_sequence_no += 1
            await self.session.flush()
            runtime.last_trigger_message_id = replacement.id
            run = self._new_run(
                game_session,
                replacement.id,
                len(replacement.recipients),
                replacement_for_message_id=target.id,
            )
        else:
            runtime.last_trigger_message_id = ooc.id
            run = self._new_run(
                game_session,
                ooc.id,
                1,
                selected_character_id=target.sender_character_id,
                replacement_for_message_id=target.id,
            )
        self.session.add(run)
        await self.session.flush()
        if get_settings().character_agent_is_configured:
            runtime.active_agent_run_id = run.id
            runtime.status = RuntimeStatus.AGENTS_EVALUATING
        else:
            run.status = AgentRunStatus.COMPLETED
            run.stop_reason = AgentRunStopReason.ALL_SILENT
            run.finished_at = datetime.now(UTC)
            runtime.status = RuntimeStatus.IDLE
        await self.session.commit()
        return await self._get_session(session_id)

    async def stop_runtime(self, session_id: str) -> GameSession:
        game_session = await self._get_session(session_id)
        if game_session.status != SessionStatus.ACTIVE:
            raise ConflictError("SESSION_ENDED", "已结束的 Session 无法停止 AI。")
        runtime = game_session.runtime
        runtime.generation += 1
        await self._cancel_active_run(runtime, AgentRunStopReason.DM_STOP)
        runtime.active_agent_run_id = None
        runtime.status = RuntimeStatus.IDLE
        runtime.waiting_message_id = None
        runtime.waiting_request = None
        runtime.last_error_code = None
        runtime.last_error_message = None
        await self.session.commit()
        return await self._get_session(session_id)

    async def retry_latest(self, session_id: str) -> GameSession:
        """Retry the last trigger after a complete Agent failure without duplicating DM text."""
        game_session = await self._get_session(session_id)
        if game_session.status != SessionStatus.ACTIVE:
            raise ConflictError("SESSION_ENDED", "已结束的 Session 无法重试 AI。")
        if game_session.runtime.status != RuntimeStatus.ERROR:
            raise ConflictError("RUNTIME_NOT_RETRYABLE", "当前 Session 没有可重试的失败事件。")
        trigger_id = game_session.runtime.last_trigger_message_id
        if trigger_id is None:
            raise ConflictError("NO_LATEST_EVENT", "当前 Session 没有可重试的事件。")
        trigger = await self.get(trigger_id)
        recipient_ids = [item.character_id for item in trigger.recipients]
        if not recipient_ids:
            raise ConflictError("NO_ELIGIBLE_CHARACTERS", "最新事件没有可响应的角色。")
        runtime = game_session.runtime
        runtime.generation += 1
        runtime.waiting_message_id = None
        runtime.waiting_request = None
        runtime.last_error_code = None
        runtime.last_error_message = None
        runtime.consecutive_ai_messages = 0
        runtime.status = RuntimeStatus.AGENTS_EVALUATING
        run = self._new_run(game_session, trigger.id, len(recipient_ids))
        self.session.add(run)
        await self.session.flush()
        if get_settings().character_agent_is_configured:
            runtime.active_agent_run_id = run.id
        else:
            run.status = AgentRunStatus.COMPLETED
            run.stop_reason = AgentRunStopReason.ALL_SILENT
            run.finished_at = datetime.now(UTC)
            runtime.status = RuntimeStatus.IDLE
        await self.session.commit()
        return await self._get_session(session_id)

    async def _cancel_active_run(self, runtime: SessionRuntime, reason: AgentRunStopReason) -> None:
        active_run_id = runtime.active_agent_run_id
        if active_run_id is None:
            return
        run = await self.session.get(AgentRun, active_run_id)
        if run is not None and run.status in {AgentRunStatus.PENDING, AgentRunStatus.RUNNING}:
            run.status = AgentRunStatus.CANCELLED
            run.stop_reason = reason
            run.finished_at = datetime.now(UTC)
        runtime.active_agent_run_id = None

    @staticmethod
    def _new_run(
        game_session: GameSession,
        trigger_message_id: str,
        eligible_count: int,
        *,
        selected_character_id: str | None = None,
        replacement_for_message_id: str | None = None,
    ) -> AgentRun:
        return AgentRun(
            campaign_id=game_session.campaign_id,
            session_id=game_session.id,
            trigger_message_id=trigger_message_id,
            generation=game_session.runtime.generation,
            status=AgentRunStatus.PENDING,
            eligible_count=eligible_count,
            selected_character_id=selected_character_id,
            replacement_for_message_id=replacement_for_message_id,
            random_seed=secrets.randbits(63),
        )

    @staticmethod
    def _resolve_recipient_ids(game_session: GameSession, payload: DmMessageCreate) -> list[str]:
        member_ids = [membership.character_id for membership in game_session.campaign.memberships]
        if payload.audience == MessageAudience.PUBLIC:
            if payload.recipient_character_ids:
                raise AppError("PUBLIC_RECIPIENTS_NOT_ALLOWED", "公开消息不能指定接收角色。")
            return member_ids
        if payload.audience != MessageAudience.PRIVATE:
            raise AppError("DM_ONLY_NOT_ALLOWED", "DM 不能发送仅 DM 可见的消息。")

        selected_ids = list(dict.fromkeys(payload.recipient_character_ids))
        if not selected_ids:
            raise AppError("PRIVATE_RECIPIENT_REQUIRED", "私密消息至少需要选择一名角色。")
        if len(selected_ids) != len(payload.recipient_character_ids):
            raise AppError("DUPLICATE_RECIPIENT", "同一角色不能被重复选择。")
        if any(character_id not in member_ids for character_id in selected_ids):
            raise AppError("RECIPIENT_NOT_IN_CAMPAIGN", "接收者必须是当前战役成员。")
        return selected_ids
