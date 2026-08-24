from __future__ import annotations

import json
import logging
from itertools import combinations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.agents.relationship_agent import (
    DeepSeekRelationshipAgent,
    RelationshipAgent,
)
from backend.app.core.config import Settings, get_settings
from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    CharacterAcquaintance,
    Message,
)
from backend.app.domain.enums import MessageKind
from backend.app.services.acquaintance_service import ordered_pair

logger = logging.getLogger(__name__)


class RelationshipService:
    """Rebuilds pair relationships from the story both characters can actually know."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings | None = None,
        agent: RelationshipAgent | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.agent = agent

    async def refresh_for_campaign(self, campaign_id: str) -> None:
        if not self.settings.relationship_agent_is_configured and self.agent is None:
            return
        campaign = await self.session.scalar(
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(
                selectinload(Campaign.memberships).selectinload(CampaignMembership.character)
            )
        )
        if campaign is None:
            return
        characters = sorted(
            (membership.character for membership in campaign.memberships),
            key=lambda item: item.id,
        )
        if len(characters) < 2:
            return

        character_ids = [item.id for item in characters]
        existing_rows = list(
            await self.session.scalars(
                select(CharacterAcquaintance).where(
                    CharacterAcquaintance.character_a_id.in_(character_ids),
                    CharacterAcquaintance.character_b_id.in_(character_ids),
                )
            )
        )
        existing = {
            (item.character_a_id, item.character_b_id): item for item in existing_rows
        }
        messages = list(
            await self.session.scalars(
                select(Message)
                .where(
                    Message.session.has(campaign_id=campaign_id),
                    Message.kind == MessageKind.IN_GAME,
                    Message.invalidated_at.is_(None),
                )
                .options(
                    selectinload(Message.sender_character),
                    selectinload(Message.recipients),
                )
                .order_by(Message.sequence_no.asc())
            )
        )
        message_recipient_ids = {
            message.id: {recipient.character_id for recipient in message.recipients}
            for message in messages
        }

        allowed_pairs: set[tuple[str, str]] = set()
        pair_contexts: list[dict[str, object]] = []
        for character_a, character_b in combinations(characters, 2):
            pair = ordered_pair(character_a.id, character_b.id)
            allowed_pairs.add(pair)
            relationship = existing.get(pair)
            shared_story = [
                {
                    "speaker": (
                        message.sender_character.name
                        if message.sender_character is not None
                        else "DM"
                    ),
                    "content": message.content,
                }
                for message in messages
                if {character_a.id, character_b.id}.issubset(
                    message_recipient_ids[message.id]
                )
            ]
            pair_contexts.append(
                {
                    "character_a": {"id": character_a.id, "name": character_a.name},
                    "character_b": {"id": character_b.id, "name": character_b.name},
                    "already_acquainted": relationship is not None,
                    "established_in_this_campaign": (
                        relationship is not None
                        and relationship.met_campaign_id == campaign.id
                    ),
                    "existing_relationship_history": (
                        relationship.relationship_history if relationship is not None else ""
                    ),
                    "complete_shared_story": shared_story,
                }
            )

        context = json.dumps(
            {"campaign": campaign.name, "allowed_pairs": pair_contexts},
            ensure_ascii=False,
            indent=2,
        )
        try:
            agent = self.agent or DeepSeekRelationshipAgent(self.settings)
            result = await agent.refresh(context)
        except Exception:
            logger.exception("Automatic relationship refresh failed: campaign_id=%s", campaign_id)
            return

        changed = False
        for update in result.output.updates:
            try:
                pair = ordered_pair(update.character_a_id, update.character_b_id)
            except Exception:
                continue
            if pair not in allowed_pairs:
                continue
            relationship = existing.get(pair)
            if not update.acquainted:
                if relationship is not None and relationship.met_campaign_id == campaign.id:
                    await self.session.delete(relationship)
                    existing.pop(pair)
                    changed = True
                continue
            history = update.relationship_history.strip()
            if not history:
                continue
            if relationship is None:
                relationship = CharacterAcquaintance(
                    character_a_id=pair[0],
                    character_b_id=pair[1],
                    met_campaign_id=campaign.id,
                    relationship_history=history,
                )
                self.session.add(relationship)
                existing[pair] = relationship
                changed = True
            elif relationship.relationship_history != history:
                relationship.relationship_history = history
                changed = True
        if changed:
            await self.session.commit()
