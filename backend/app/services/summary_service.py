from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.agents.summary_agent import DeepSeekSummaryAgent
from backend.app.core.config import get_settings
from backend.app.db.models import (
    CampaignMembership,
    CharacterMemory,
    GameSession,
    SessionSummary,
)
from backend.app.domain.enums import MemoryOrigin, SummaryAudience
from backend.app.services.message_projection import EffectiveMessageProjection


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
            memories: list[str] = []
            settings = get_settings()
            if settings.summary_agent_is_configured:
                try:
                    result = await DeepSeekSummaryAgent(settings).summarize(record)
                    record = result.output.summary
                    memories = [item.strip() for item in result.output.memories if item.strip()]
                except Exception:
                    # Session completion must remain successful when the provider is unavailable.
                    pass
            await self._upsert(
                game_session.id,
                membership.character_id,
                SummaryAudience.CHARACTER,
                record,
            )
            for content in memories:
                self.session.add(
                    CharacterMemory(
                        character_id=membership.character_id,
                        origin=MemoryOrigin.AUTO,
                        content=content,
                        source_campaign_id=game_session.campaign_id,
                        source_session_id=game_session.id,
                    )
                )

    async def _record(self, session_id: str, character_id: str | None = None) -> str:
        messages = await EffectiveMessageProjection.session_messages(
            self.session, session_id, character_id
        )
        messages = messages[:80]
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
