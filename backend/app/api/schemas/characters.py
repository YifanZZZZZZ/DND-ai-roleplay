from datetime import datetime

from pydantic import Field, field_validator

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import MemoryOrigin, ProfileStatus, SkillName

ALL_SKILLS = frozenset(SkillName)


class CharacterCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=120)
    roleplay_prompt: str = Field(min_length=1, max_length=200_000)
    voice_samples: str = Field(default="", max_length=20_000)
    narration_notes: str = Field(default="", max_length=4_000)
    max_hp: int = Field(gt=0, le=100_000)


class CharacterUpdate(ApiSchema):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    roleplay_prompt: str | None = Field(default=None, min_length=1, max_length=200_000)
    voice_samples: str | None = Field(default=None, max_length=20_000)
    narration_notes: str | None = Field(default=None, max_length=4_000)
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
    voice_samples: str
    narration_notes: str
    profile_content: str
    profile_status: ProfileStatus


class SkillSetUpdate(ApiSchema):
    revision: int = Field(ge=1)
    modifiers: dict[SkillName, int]

    @field_validator("modifiers")
    @classmethod
    def validate_modifiers(cls, value: dict[SkillName, int]) -> dict[SkillName, int]:
        if frozenset(value) != ALL_SKILLS:
            raise ValueError("必须完整填写十八项标准技能，且不能包含其他技能。")
        return value


class SkillSetView(ApiSchema):
    character_id: str
    revision: int
    modifiers: dict[SkillName, int]
    updated_at: datetime


class CampaignSkillMemberView(ApiSchema):
    character_id: str
    name: str
    modifiers: dict[SkillName, int]


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
