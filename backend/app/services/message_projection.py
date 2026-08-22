from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Message, MessageRecipient
from backend.app.domain.enums import MessageKind


class EffectiveMessageProjection:
    """Single source of truth for published, non-OOC messages."""

    @staticmethod
    def for_session(session_id: str, character_id: str | None = None):
        query = (
            select(Message)
            .where(
                Message.session_id == session_id,
                Message.kind != MessageKind.OOC,
                Message.invalidated_at.is_(None),
            )
            .options(
                selectinload(Message.sender_character),
                selectinload(Message.recipients).selectinload(MessageRecipient.character),
            )
            .order_by(Message.sequence_no)
        )
        if character_id is not None:
            query = query.join(MessageRecipient).where(
                MessageRecipient.character_id == character_id
            )
        return query

    @staticmethod
    def for_campaign(campaign_id: str):
        return (
            select(Message)
            .where(
                Message.session.has(campaign_id=campaign_id),
                Message.kind != MessageKind.OOC,
                Message.invalidated_at.is_(None),
            )
            .options(selectinload(Message.recipients).selectinload(MessageRecipient.character))
            .order_by(Message.created_at)
        )

    @classmethod
    async def session_messages(
        cls, session: AsyncSession, session_id: str, character_id: str | None = None
    ) -> list[Message]:
        return list(await session.scalars(cls.for_session(session_id, character_id)))

    @classmethod
    async def campaign_messages(cls, session: AsyncSession, campaign_id: str) -> list[Message]:
        return list(await session.scalars(cls.for_campaign(campaign_id)))
