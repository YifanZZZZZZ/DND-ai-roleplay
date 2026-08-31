from __future__ import annotations

import json
import logging
from itertools import permutations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.agents.relationship_agent import DeepSeekRelationshipAgent, RelationshipAgent
from backend.app.core.config import Settings, get_settings
from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    CharacterRelationship,
    Message,
)
from backend.app.domain.enums import MessageKind

logger = logging.getLogger(__name__)


class RelationshipService:
    """Incrementally maintains each player's subjective view of another player."""

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
            .options(selectinload(Campaign.memberships).selectinload(CampaignMembership.character))
        )
        if campaign is None:
            return
        characters = sorted(
            (membership.character for membership in campaign.memberships),
            key=lambda item: item.id,
        )
        # NPCs are intentionally absent, and a solo campaign has no player-to-player edge.
        if len(characters) < 2:
            return

        character_ids = [item.id for item in characters]
        existing_rows = list(
            await self.session.scalars(
                select(CharacterRelationship).where(
                    CharacterRelationship.owner_character_id.in_(character_ids),
                    CharacterRelationship.target_character_id.in_(character_ids),
                )
            )
        )
        existing = {
            (item.owner_character_id, item.target_character_id): item for item in existing_rows
        }
        messages = list(
            await self.session.scalars(
                select(Message)
                .where(
                    Message.session.has(campaign_id=campaign_id),
                    Message.kind == MessageKind.IN_GAME,
                    Message.invalidated_at.is_(None),
                )
                .options(selectinload(Message.sender_character), selectinload(Message.recipients))
                .order_by(Message.created_at.asc(), Message.sequence_no.asc())
            )
        )
        if not messages:
            return
        sequence = {message.id: index for index, message in enumerate(messages)}
        recipient_ids = {
            message.id: {recipient.character_id for recipient in message.recipients}
            for message in messages
        }

        allowed: set[tuple[str, str]] = set()
        contexts: list[dict[str, object]] = []
        latest_by_direction: dict[tuple[str, str], str] = {}
        for owner, target in permutations(characters, 2):
            direction = (owner.id, target.id)
            allowed.add(direction)
            relationship = existing.get(direction)
            last_index = (
                sequence.get(relationship.last_processed_message_id, -1)
                if relationship is not None
                else -1
            )
            shared = [
                message
                for index, message in enumerate(messages)
                if index > last_index
                and {owner.id, target.id}.issubset(recipient_ids[message.id])
            ]
            if not shared:
                continue
            latest_by_direction[direction] = shared[-1].id
            contexts.append(
                {
                    "owner": {"id": owner.id, "name": owner.name},
                    "target": {"id": target.id, "name": target.name},
                    "already_acquainted": relationship is not None,
                    "established_in_this_campaign": (
                        relationship is not None and relationship.met_campaign_id == campaign.id
                    ),
                    "existing_current_view": (
                        relationship.current_view if relationship is not None else ""
                    ),
                    "existing_important_history": (
                        relationship.important_history if relationship is not None else []
                    ),
                    "new_shared_story": [
                        {
                            "speaker": (
                                message.sender_character.name
                                if message.sender_character is not None
                                else "DM"
                            ),
                            "content": message.content,
                        }
                        for message in shared
                    ],
                }
            )
        if not contexts:
            return

        context = json.dumps(
            {"campaign": campaign.name, "allowed_directions": contexts},
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
        seen: set[tuple[str, str]] = set()
        for update in result.output.updates:
            direction = (update.owner_character_id, update.target_character_id)
            if direction not in allowed or direction in seen:
                continue
            seen.add(direction)
            relationship = existing.get(direction)
            latest_message_id = latest_by_direction.get(direction)
            if relationship is not None and latest_message_id is not None:
                relationship.last_processed_message_id = latest_message_id
                changed = True
            if not update.acquainted:
                if relationship is not None and relationship.met_campaign_id == campaign.id:
                    await self.session.delete(relationship)
                    existing.pop(direction)
                    changed = True
                continue
            if not update.changed and relationship is not None:
                continue
            current_view = update.current_view.strip()
            important_history = [
                item.strip() for item in update.important_history if item.strip()
            ][:6]
            if not current_view:
                continue
            if relationship is None:
                relationship = CharacterRelationship(
                    owner_character_id=direction[0],
                    target_character_id=direction[1],
                    met_campaign_id=campaign.id,
                    current_view=current_view,
                    important_history=important_history,
                    last_processed_message_id=latest_message_id,
                )
                self.session.add(relationship)
                existing[direction] = relationship
                changed = True
            elif update.changed:
                relationship.current_view = current_view
                relationship.important_history = important_history
                changed = True
        if changed:
            await self.session.commit()
