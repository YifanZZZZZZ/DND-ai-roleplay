from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas.characters import SkillSetUpdate
from backend.app.core.errors import ConflictError, NotFoundError
from backend.app.db.models import Character, CharacterSkillSet
from backend.app.domain.enums import SkillName
from backend.app.services.edit_lock import ensure_character_editable

DEFAULT_SKILL_MODIFIERS = {skill.value: 0 for skill in SkillName}


class SkillService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, character_id: str) -> CharacterSkillSet:
        character = await self.session.get(Character, character_id)
        if character is None:
            raise NotFoundError("Character", character_id)
        skill_set = await self.session.get(CharacterSkillSet, character_id)
        if skill_set is None:
            skill_set = CharacterSkillSet(
                character_id=character_id,
                modifiers=dict(DEFAULT_SKILL_MODIFIERS),
            )
            self.session.add(skill_set)
            await self.session.commit()
        return skill_set

    async def update(self, character_id: str, payload: SkillSetUpdate) -> CharacterSkillSet:
        await ensure_character_editable(self.session, character_id)
        skill_set = await self.get(character_id)
        if skill_set.revision != payload.revision:
            raise ConflictError(
                "SKILL_SET_REVISION_CONFLICT",
                "技能加值已在其他页面发生变化，请刷新后重试。",
            )
        skill_set.modifiers = {
            skill.value: modifier for skill, modifier in payload.modifiers.items()
        }
        skill_set.revision += 1
        await self.session.commit()
        return await self.get(character_id)
