from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db.engine import async_session_factory
from backend.app.events import get_session_event_hub
from backend.app.services.dm_draft_service import DmDraftService

logger = logging.getLogger(__name__)


class DmDraftSupervisor:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession] = async_session_factory
    ) -> None:
        self._session_factory = session_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def start(self, message_id: str, session_id: str) -> None:
        if message_id in self._tasks and not self._tasks[message_id].done():
            return
        task = asyncio.create_task(
            self._execute(message_id, session_id), name=f"ai-dm-draft:{message_id}"
        )
        self._tasks[message_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(message_id, None))

    async def _execute(self, message_id: str, session_id: str) -> None:
        try:
            async with self._session_factory() as session:
                draft = await DmDraftService(session).generate_for_character_reply(message_id)
                if draft is not None:
                    await get_session_event_hub().publish("dm_draft.changed", session_id)
                    await get_session_event_hub().publish("runtime.changed", session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "AI DM draft generation failed: message_id=%s session_id=%s",
                message_id,
                session_id,
            )
            await get_session_event_hub().publish("dm_draft.failed", session_id)
            await get_session_event_hub().publish("runtime.changed", session_id)

    async def recover_interrupted_drafts(self) -> None:
        # Drafts are deliberately not replayed after a process restart. A DM can
        # explicitly request regeneration from the latest formal character reply.
        from backend.app.db.models import CampaignDmDraft
        from backend.app.domain.enums import DmDraftStatus

        async with self._session_factory() as session:
            drafts = list(
                await session.scalars(
                    select(CampaignDmDraft).where(
                        CampaignDmDraft.status == DmDraftStatus.GENERATING
                    )
                )
            )
            for draft in drafts:
                draft.status = DmDraftStatus.FAILED
                draft.content = "AI DM 进程中断，请重新生成草稿。"
            if drafts:
                await session.commit()


_dm_draft_supervisor = DmDraftSupervisor()


def get_dm_draft_supervisor() -> DmDraftSupervisor:
    return _dm_draft_supervisor
