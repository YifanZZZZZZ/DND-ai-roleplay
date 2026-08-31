from dataclasses import dataclass
from itertools import combinations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Character, CharacterRelationship
from backend.app.services.campaign_service import CampaignService


@dataclass(frozen=True, slots=True)
class RelationshipPair:
    character_a: Character
    character_b: Character
    a_to_b: CharacterRelationship | None
    b_to_a: CharacterRelationship | None

    @property
    def acquainted(self) -> bool:
        return self.a_to_b is not None or self.b_to_a is not None


class AcquaintanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_campaign(
        self, campaign_id: str
    ) -> list[RelationshipPair]:
        campaign = await CampaignService(self.session).get(campaign_id)
        characters = sorted(
            (membership.character for membership in campaign.memberships),
            key=lambda character: (character.name, character.id),
        )
        ids = [character.id for character in characters]
        rows = list(
            await self.session.scalars(
                select(CharacterRelationship).where(
                    CharacterRelationship.owner_character_id.in_(ids),
                    CharacterRelationship.target_character_id.in_(ids),
                )
            )
        )
        relationships = {
            (row.owner_character_id, row.target_character_id): row for row in rows
        }
        return [
            RelationshipPair(
                character_a=character_a,
                character_b=character_b,
                a_to_b=relationships.get((character_a.id, character_b.id)),
                b_to_a=relationships.get((character_b.id, character_a.id)),
            )
            for character_a, character_b in combinations(characters, 2)
        ]

    async def acquainted_character_ids(self, character_id: str) -> set[str]:
        rows = list(
            await self.session.scalars(
                select(CharacterRelationship).where(
                    or_(
                        CharacterRelationship.owner_character_id == character_id,
                        CharacterRelationship.target_character_id == character_id,
                    )
                )
            )
        )
        return {
            row.target_character_id
            if row.owner_character_id == character_id
            else row.owner_character_id
            for row in rows
        }
