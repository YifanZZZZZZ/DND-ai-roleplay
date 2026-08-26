from pydantic import Field, field_validator

from backend.app.api.schemas.base import ApiSchema


class CharacterSpellInput(ApiSchema):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="MANUAL", max_length=40)
    summary: str = Field(min_length=1, max_length=1000)


def validate_spellbook(value: list[CharacterSpellInput]) -> list[CharacterSpellInput]:
    names = [spell.name.strip().casefold() for spell in value]
    if len(names) != len(set(names)):
        raise ValueError("法术名称不能重复。")
    return value


class CharacterSpellbookUpdate(ApiSchema):
    revision: int = Field(ge=1)
    spells: list[CharacterSpellInput] = Field(default_factory=list, max_length=200)

    _validate_spells = field_validator("spells")(validate_spellbook)


class CharacterSpellbookView(ApiSchema):
    character_id: str
    revision: int
    spells: list[CharacterSpellInput]
