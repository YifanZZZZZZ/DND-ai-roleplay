from datetime import datetime

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import CampaignLifecycleStatus, RuntimeStatus, SessionStatus


class CampaignCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=20_000)
    character_ids: list[str] = Field(default_factory=list, max_length=6)


class CampaignUpdate(ApiSchema):
    revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=20_000)


class CampaignMembershipUpdate(ApiSchema):
    revision: int = Field(ge=1)
    character_ids: list[str] = Field(max_length=6)


class CampaignMember(ApiSchema):
    character_id: str
    name: str
    max_hp: int
    avatar_path: str | None
    is_configured: bool


class SessionSummary(ApiSchema):
    id: str
    title: str
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None


class CampaignSummary(ApiSchema):
    id: str
    name: str
    description: str | None
    lifecycle_status: CampaignLifecycleStatus
    archived_at: datetime | None
    revision: int
    member_count: int
    active_session_id: str | None
    created_at: datetime
    updated_at: datetime


class CampaignDetail(CampaignSummary):
    members: list[CampaignMember]
    sessions: list[SessionSummary]


class SessionCreate(ApiSchema):
    title: str = Field(min_length=1, max_length=160)


class HpState(ApiSchema):
    character_id: str
    name: str
    current_hp: int
    max_hp: int


class HpUpdate(ApiSchema):
    current_hp: int = Field(ge=0, le=100_000)


class SessionDetail(ApiSchema):
    id: str
    campaign_id: str
    title: str
    status: SessionStatus
    runtime_status: RuntimeStatus
    runtime_generation: int
    active_agent_run_id: str | None
    waiting_request: str | None
    consecutive_ai_messages: int
    hp_states: list[HpState]
    started_at: datetime
    ended_at: datetime | None
