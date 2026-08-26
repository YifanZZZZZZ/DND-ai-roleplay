from datetime import datetime

from pydantic import Field, field_validator

from backend.app.api.schemas.base import ApiSchema
from backend.app.api.schemas.spells import CharacterSpellInput, validate_spellbook
from backend.app.domain.enums import SheetParseStatus
from backend.app.files.sheet_parser import CharacterSheetSnapshot


class SheetPreview(ApiSchema):
    version_id: str
    parse_status: SheetParseStatus
    original_filename: str
    snapshot: CharacterSheetSnapshot
    spellbook: list[CharacterSpellInput]
    created_at: datetime


class SheetActivationRequest(ApiSchema):
    spellbook: list[CharacterSpellInput] = Field(default_factory=list, max_length=200)

    _validate_spellbook = field_validator("spellbook")(validate_spellbook)


class SheetActivation(ApiSchema):
    character_id: str
    active_version_id: str
    snapshot: CharacterSheetSnapshot
    spellbook: list[CharacterSpellInput]
