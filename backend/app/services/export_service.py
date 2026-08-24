from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import (
    Campaign,
    CampaignDmDraft,
    CampaignMembership,
    Character,
    CharacterAcquaintance,
    CharacterMemory,
    CharacterSheetVersion,
    SessionSummary,
    SkillCheck,
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
        relationships = list(
            await self.session.scalars(
                select(CharacterAcquaintance).where(
                    or_(
                        CharacterAcquaintance.character_a_id == character.id,
                        CharacterAcquaintance.character_b_id == character.id,
                    )
                )
            )
        )
        related_ids = {
            item.character_b_id
            if item.character_a_id == character.id
            else item.character_a_id
            for item in relationships
        }
        related_characters = {
            item.id: item
            for item in list(
                await self.session.scalars(select(Character).where(Character.id.in_(related_ids)))
            )
        }
        return {
            "character": {
                "id": character.id,
                "name": character.name,
                "roleplayPrompt": character.roleplay_prompt,
                "developmentProfile": character.profile.content,
                "sheetSnapshot": sheet.parsed_snapshot if sheet is not None else None,
            },
            "memories": [self._memory(memory) for memory in character.memories],
            "relationships": [
                {
                    "characterId": related_id,
                    "characterName": related_characters[related_id].name,
                    "relationshipHistory": item.relationship_history,
                }
                for item in relationships
                if (related_id := (
                    item.character_b_id
                    if item.character_a_id == character.id
                    else item.character_a_id
                )) in related_characters
            ],
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
        skill_checks = list(
            await self.session.scalars(
                select(SkillCheck).where(SkillCheck.campaign_id == campaign_id)
            )
        )
        drafts = list(
            await self.session.scalars(
                select(CampaignDmDraft).where(CampaignDmDraft.campaign_id == campaign_id)
            )
        )
        relationships = list(
            await self.session.scalars(
                select(CharacterAcquaintance).where(
                    CharacterAcquaintance.character_a_id.in_(member_ids),
                    CharacterAcquaintance.character_b_id.in_(member_ids),
                )
            )
        )
        return {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "lifecycleStatus": campaign.lifecycle_status,
                "dmGuide": campaign.dm_guide,
                "sceneNotes": campaign.scene_notes,
                "moduleContent": campaign.module_content,
                "styleInstructions": campaign.style_instructions,
                "openingInstructions": campaign.opening_instructions,
                "playMode": campaign.play_mode,
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
            "characterRelationships": [
                {
                    "characterAId": item.character_a_id,
                    "characterBId": item.character_b_id,
                    "relationshipHistory": item.relationship_history,
                }
                for item in relationships
            ],
            "skillChecks": [
                {
                    "id": item.id,
                    "characterId": item.character_id,
                    "skill": item.skill,
                    "rollMode": item.roll_mode,
                    "dieOne": item.die_one,
                    "dieTwo": item.die_two,
                    "selectedDie": item.selected_die,
                    "total": item.total,
                    "dc": item.dc,
                    "systemOutcome": item.system_outcome,
                    "dmAdjudication": item.dm_adjudication,
                    "status": item.status,
                    "reason": item.reason,
                    "createdAt": item.created_at,
                }
                for item in skill_checks
            ],
            "dmDrafts": [
                {
                    "id": item.id,
                    "content": item.content,
                    "status": item.status,
                    "sourceSkillCheckId": item.source_skill_check_id,
                    "createdAt": item.created_at,
                    "updatedAt": item.updated_at,
                }
                for item in drafts
            ],
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
