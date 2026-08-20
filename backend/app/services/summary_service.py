from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import (
    CampaignMembership,
    GameSession,
    Message,
    MessageRecipient,
    SessionSummary,
)
from backend.app.domain.enums import MessageKind, SummaryAudience


class SummaryService:
    """Builds editable, privacy-filtered session records without hidden model state."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build_for_session(self, game_session: GameSession) -> None:
        members = list(
            await self.session.scalars(
                select(CampaignMembership).where(
                    CampaignMembership.campaign_id == game_session.campaign_id
                )
            )
        )
        await self._upsert(
            game_session.id,
            None,
            SummaryAudience.DM,
            await self._record(game_session.id),
        )
        for membership in members:
            record = await self._record(game_session.id, membership.character_id)
            await self._upsert(
                game_session.id,
                membership.character_id,
                SummaryAudience.CHARACTER,
                record,
            )

    async def _record(self, session_id: str, character_id: str | None = None) -> str:
        query = (
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.kind != MessageKind.OOC,
                Message.invalidated_at.is_(None),
            )
            .order_by(Message.sequence_no)
        )
        if character_id is not None:
            query = query.join(MessageRecipient).where(
                MessageRecipient.character_id == character_id
            )
        messages = list(await self.session.scalars(query.limit(80)))
        lines = [message.content.strip() for message in messages if message.content.strip()]
        return "本节可见事实记录：\n" + "\n".join(lines)[:12000]

    async def _upsert(
        self, session_id: str, character_id: str | None, audience: SummaryAudience, content: str
    ) -> None:
        existing = await self.session.scalar(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id,
                SessionSummary.character_id == character_id,
                SessionSummary.audience == audience,
            )
        )
        if existing is None:
            self.session.add(
                SessionSummary(
                    session_id=session_id,
                    character_id=character_id,
                    audience=audience,
                    content=content,
                )
            )
        else:
            existing.content = content
            existing.revision += 1
