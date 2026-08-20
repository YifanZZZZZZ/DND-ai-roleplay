from datetime import datetime

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import MemoryOrigin, ProfileStatus


class CharacterCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=120)
    roleplay_prompt: str = Field(min_length=1, max_length=200_000)
    max_hp: int = Field(gt=0, le=100_000)


class CharacterUpdate(ApiSchema):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    roleplay_prompt: str | None = Field(default=None, min_length=1, max_length=200_000)
    max_hp: int | None = Field(default=None, gt=0, le=100_000)
    profile_content: str | None = Field(default=None, max_length=200_000)


class CharacterSummary(ApiSchema):
    id: str
    name: str
    max_hp: int
    avatar_path: str | None
    has_roleplay_prompt: bool
    has_active_sheet: bool
    revision: int
    created_at: datetime
    updated_at: datetime


class CharacterDetail(CharacterSummary):
    roleplay_prompt: str
    profile_content: str
    profile_status: ProfileStatus


class MemoryCreate(ApiSchema):
    content: str = Field(min_length=1, max_length=5000)
    pinned: bool = False


class MemoryUpdate(ApiSchema):
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    pinned: bool | None = None


class MemoryView(ApiSchema):
    id: str
    character_id: str
    source_campaign_id: str | None
    source_session_id: str | None
    origin: MemoryOrigin
    content: str
    pinned: bool
    created_at: datetime
    updated_at: datetime
