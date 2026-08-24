from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import (
    RollMode,
    SkillCheckDmAdjudication,
    SkillCheckStatus,
    SkillCheckSystemOutcome,
    SkillName,
)


class SkillCheckCreate(ApiSchema):
    character_id: str
    skill: SkillName
    roll_mode: RollMode = RollMode.NORMAL
    dc: int | None = Field(default=None, ge=0, le=1000)
    reason: str | None = Field(default=None, max_length=1000)
    client_request_id: UUID


class SkillCheckAdjudicate(ApiSchema):
    outcome: SkillCheckDmAdjudication


class SkillCheckVoid(ApiSchema):
    reason: str = Field(min_length=1, max_length=1000)


class SkillCheckView(ApiSchema):
    id: str
    campaign_id: str
    character_id: str
    character_name: str
    skill: SkillName
    modifier_snapshot: int
    roll_mode: RollMode
    die_one: int
    die_two: int | None
    selected_die: int
    total: int
    dc: int | None
    system_outcome: SkillCheckSystemOutcome
    dm_adjudication: SkillCheckDmAdjudication | None
    reason: str | None
    status: SkillCheckStatus
    void_reason: str | None
    created_at: datetime
    adjudicated_at: datetime | None
