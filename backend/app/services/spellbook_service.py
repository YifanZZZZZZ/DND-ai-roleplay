from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.schemas.spells import (
    CharacterSpellbookUpdate,
    CharacterSpellbookView,
    CharacterSpellInput,
)
from backend.app.core.errors import ConflictError
from backend.app.db.models import Character
from backend.app.files.sheet_parser import CharacterSheetSnapshot, SpellSnapshot
from backend.app.services.character_service import CharacterService
from backend.app.services.edit_lock import ensure_character_editable

_WHITESPACE = re.compile(r"\s+")
_DICE = re.compile(r"\b\d+d(?:4|6|8|10|12|20|100)\b", re.I)
_MEASURE = re.compile(r"\d+(?:\.\d+)?\s*(?:尺|英尺|米|公里|轮|分钟|小时|天|点)")
_BARE_NUMBER = re.compile(r"\d+")
_RULE_WORDS = (
    (re.compile(r"豁免(?:检定)?"), "尝试抵抗"),
    (re.compile(r"进行一次[^，。；]{0,12}检定"), "进行相应尝试"),
    (re.compile(r"法术位"), "施法能力"),
    (re.compile(r"难度等级|\bDC\b|\bAC\b", re.I), "相应难度"),
    (re.compile(r"回合"), "短时间"),
)


def narrative_spell_summary(spell: SpellSnapshot) -> str:
    """Turn sheet rules prose into compact, number-free narrative guidance.

    This is deliberately deterministic: upload and activation must still work
    without an LLM connection. The DM edits the result in the preview before it
    becomes the character's closed whitelist.
    """

    text = _WHITESPACE.sub(" ", spell.description).strip()
    if text:
        text = _DICE.sub("相应效果", text)
        text = _MEASURE.sub("一定范围或时间", text)
        text = _BARE_NUMBER.sub("", text)
        for pattern, replacement in _RULE_WORDS:
            text = pattern.sub(replacement, text)
        text = text.strip(" ，。；：")
    if not text:
        text = f"施展{spell.name}，具体用途与外部结果由 DM 根据场景裁定"
    if len(text) > 480:
        text = text[:480].rsplit("。", 1)[0].rstrip("，；： ")
    return text + ("。" if not text.endswith(("。", "！", "？")) else "")


def spellbook_from_snapshot(snapshot: CharacterSheetSnapshot) -> list[CharacterSpellInput]:
    return [
        CharacterSpellInput(
            name=spell.name.strip(),
            category=spell.category,
            summary=narrative_spell_summary(spell),
        )
        for spell in snapshot.spells
    ]


def normalized_spellbook(spells: list[CharacterSpellInput]) -> list[dict[str, str]]:
    return [
        {
            "name": spell.name.strip(),
            "category": spell.category.strip() or "MANUAL",
            "summary": spell.summary.strip(),
        }
        for spell in spells
    ]


class SpellbookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, character_id: str) -> CharacterSpellbookView:
        character = await CharacterService(self.session).get(character_id)
        return self._view(character)

    async def update(
        self, character_id: str, payload: CharacterSpellbookUpdate
    ) -> CharacterSpellbookView:
        character = await CharacterService(self.session).get(character_id)
        await ensure_character_editable(self.session, character_id)
        if character.revision != payload.revision:
            raise ConflictError(
                "CHARACTER_REVISION_CONFLICT",
                "角色已在其他页面发生变化，请刷新后重试。",
            )
        character.spellbook = normalized_spellbook(payload.spells)
        character.revision += 1
        await self.session.commit()
        return self._view(character)

    @staticmethod
    def _view(character: Character) -> CharacterSpellbookView:
        return CharacterSpellbookView(
            character_id=character.id,
            revision=character.revision,
            spells=[CharacterSpellInput.model_validate(item) for item in character.spellbook],
        )
