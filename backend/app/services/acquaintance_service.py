from itertools import combinations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import AppError
from backend.app.db.models import Character, CharacterAcquaintance
from backend.app.services.campaign_service import CampaignService


def ordered_pair(character_a_id: str, character_b_id: str) -> tuple[str, str]:
    if character_a_id == character_b_id:
        raise AppError("INVALID_ACQUAINTANCE_PAIR", "角色不能与自己建立相识关系。")
    if character_a_id < character_b_id:
        return character_a_id, character_b_id
    return character_b_id, character_a_id


class AcquaintanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_campaign(
        self, campaign_id: str
    ) -> list[tuple[Character, Character, CharacterAcquaintance | None]]:
        campaign = await CampaignService(self.session).get(campaign_id)
        characters = sorted(
            (membership.character for membership in campaign.memberships),
            key=lambda character: (character.name, character.id),
        )
        ids = [character.id for character in characters]
        rows = list(
            await self.session.scalars(
                select(CharacterAcquaintance).where(
                    CharacterAcquaintance.character_a_id.in_(ids),
                    CharacterAcquaintance.character_b_id.in_(ids),
                )
            )
        )
        acquaintances = {
            (row.character_a_id, row.character_b_id): row for row in rows
        }
        return [
            (
                character_a,
                character_b,
                acquaintances.get(ordered_pair(character_a.id, character_b.id)),
            )
            for character_a, character_b in combinations(characters, 2)
        ]

    async def acquainted_character_ids(self, character_id: str) -> set[str]:
        rows = list(
            await self.session.scalars(
                select(CharacterAcquaintance).where(
                    or_(
                        CharacterAcquaintance.character_a_id == character_id,
                        CharacterAcquaintance.character_b_id == character_id,
                    )
                )
            )
        )
        return {
            row.character_b_id
            if row.character_a_id == character_id
            else row.character_a_id
            for row in rows
        }
