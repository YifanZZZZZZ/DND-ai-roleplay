from datetime import datetime

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import SheetParseStatus
from backend.app.files.sheet_parser import CharacterSheetSnapshot


class SheetPreview(ApiSchema):
    version_id: str
    parse_status: SheetParseStatus
    original_filename: str
    snapshot: CharacterSheetSnapshot
    created_at: datetime


class SheetActivation(ApiSchema):
    character_id: str
    active_version_id: str
    snapshot: CharacterSheetSnapshot
