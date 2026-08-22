from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import (
    Campaign,
    CampaignMembership,
    Character,
    CharacterMemory,
    CharacterSheetVersion,
    SessionSummary,
)
from backend.app.services.message_projection import EffectiveMessageProjection


class ExportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def character(self, character_id: str) -> dict[str, object]:
        character = await self.session.scalar(
            select(Character)
            .where(Character.id == character_id)
            .options(selectinload(Character.profile), selectinload(Character.memories))
        )
        if character is None:
            from backend.app.core.errors import NotFoundError

            raise NotFoundError("Character", character_id)
        sheet = await self.session.get(CharacterSheetVersion, character.active_sheet_version_id)
        return {
            "character": {
                "id": character.id,
                "name": character.name,
                "roleplayPrompt": character.roleplay_prompt,
                "developmentProfile": character.profile.content,
                "sheetSnapshot": sheet.parsed_snapshot if sheet is not None else None,
            },
            "memories": [self._memory(memory) for memory in character.memories],
        }

    async def campaign(self, campaign_id: str) -> dict[str, object]:
        campaign = await self.session.scalar(
            select(Campaign)
            .where(Campaign.id == campaign_id)
            .options(selectinload(Campaign.memberships).selectinload(CampaignMembership.character))
        )
        if campaign is None:
            from backend.app.core.errors import NotFoundError

            raise NotFoundError("Campaign", campaign_id)
        messages = await EffectiveMessageProjection.campaign_messages(self.session, campaign_id)
        summaries = list(
            await self.session.scalars(
                select(SessionSummary).where(SessionSummary.session.has(campaign_id=campaign_id))
            )
        )
        member_ids = [membership.character_id for membership in campaign.memberships]
        memories = list(
            await self.session.scalars(
                select(CharacterMemory).where(
                    CharacterMemory.character_id.in_(member_ids),
                    CharacterMemory.source_campaign_id == campaign_id,
                )
            )
        )
        return {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
            },
            "characters": [
                {
                    "id": item.character.id,
                    "name": item.character.name,
                    "roleplayPrompt": item.character.roleplay_prompt,
                }
                for item in campaign.memberships
            ],
            "messages": [
                {
                    "id": item.id,
                    "senderType": item.sender_type,
                    "senderCharacterId": item.sender_character_id,
                    "audience": item.audience,
                    "content": item.content,
                    "recipients": [recipient.character_id for recipient in item.recipients],
                    "isOocCorrected": item.ooc_correction_note is not None,
                }
                for item in messages
            ],
            "summaries": [
                {
                    "audience": item.audience,
                    "characterId": item.character_id,
                    "content": item.content,
                }
                for item in summaries
            ],
            "memories": [self._memory(item) for item in memories],
        }

    @staticmethod
    def _memory(memory: CharacterMemory) -> dict[str, object]:
        return {
            "id": memory.id,
            "origin": memory.origin,
            "content": memory.content,
            "pinned": memory.pinned,
            "sourceCampaignId": memory.source_campaign_id,
            "sourceSessionId": memory.source_session_id,
        }
