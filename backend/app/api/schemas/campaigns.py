from datetime import datetime

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import CampaignLifecycleStatus, CampaignPlayMode, RuntimeStatus


class CampaignCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=20_000)
    dm_guide: str = Field(default="", max_length=100_000)
    scene_notes: str = Field(default="", max_length=100_000)
    module_content: str = Field(default="", max_length=500_000)
    style_instructions: str = Field(default="", max_length=20_000)
    opening_instructions: str = Field(default="", max_length=20_000)
    character_ids: list[str] = Field(default_factory=list, max_length=6)


class CampaignUpdate(ApiSchema):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=20_000)
    dm_guide: str | None = Field(default=None, max_length=100_000)
    scene_notes: str | None = Field(default=None, max_length=100_000)
    module_content: str | None = Field(default=None, max_length=500_000)
    style_instructions: str | None = Field(default=None, max_length=20_000)
    opening_instructions: str | None = Field(default=None, max_length=20_000)
    play_mode: CampaignPlayMode | None = None


class CampaignMembershipUpdate(ApiSchema):
    revision: int = Field(ge=1)
    character_ids: list[str] = Field(max_length=6)


class CampaignMemberAdd(ApiSchema):
    revision: int = Field(ge=1)
    character_id: str


class CampaignMember(ApiSchema):
    character_id: str
    name: str
    max_hp: int
    avatar_path: str | None
    is_configured: bool


class CharacterAcquaintanceView(ApiSchema):
    character_a_id: str
    character_a_name: str
    character_b_id: str
    character_b_name: str
    acquainted: bool
    relationship_history: str


class CampaignSummary(ApiSchema):
    id: str
    name: str
    description: str | None
    dm_guide: str
    scene_notes: str
    module_content: str
    style_instructions: str
    opening_instructions: str
    play_mode: CampaignPlayMode
    lifecycle_status: CampaignLifecycleStatus
    archived_at: datetime | None
    revision: int
    member_count: int
    has_runtime: bool
    created_at: datetime
    updated_at: datetime


class CampaignDetail(CampaignSummary):
    members: list[CampaignMember]


class SessionCreate(ApiSchema):
    """Legacy internal payload retained only for migration compatibility."""

    title: str = Field(min_length=1, max_length=160)


class HpState(ApiSchema):
    character_id: str
    name: str
    current_hp: int
    max_hp: int


class HpUpdate(ApiSchema):
    current_hp: int = Field(ge=0, le=100_000)


class CampaignPlayState(ApiSchema):
    campaign_id: str
    lifecycle_status: CampaignLifecycleStatus
    runtime_status: RuntimeStatus
    runtime_generation: int
    active_agent_run_id: str | None
    waiting_request: str | None
    last_error_code: str | None
    last_error_message: str | None
    consecutive_ai_messages: int
    hp_states: list[HpState]
    started_at: datetime
    ended_at: datetime | None
