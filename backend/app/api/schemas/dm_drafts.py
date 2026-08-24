from datetime import datetime
from typing import Literal

from pydantic import Field

from backend.app.api.schemas.base import ApiSchema
from backend.app.api.schemas.messages import MessageView
from backend.app.domain.enums import DmDraftStatus, DmDraftTriggerType, MessageAudience


class DmDraftCreate(ApiSchema):
    """`prompt` is the DM's own rough reply or a one-line intent."""

    prompt: str = Field(min_length=1, max_length=6000)
    source_skill_check_id: str | None = None
    assist_mode: str = Field(default="POLISH", pattern="^(POLISH|EXPAND|REWRITE)$")


class DmDraftUpdate(ApiSchema):
    revision: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=1200)
    audience: Literal["PUBLIC", "PRIVATE"] = "PUBLIC"
    recipient_character_ids: list[str] = Field(default_factory=list, max_length=6)


class DmDraftView(ApiSchema):
    id: str
    campaign_id: str
    session_id: str | None
    content: str
    audience: MessageAudience
    recipient_character_ids: list[str]
    improvised_notes: list[str]
    status: DmDraftStatus
    revision: int
    source_skill_check_id: str | None
    source_message_id: str | None
    trigger_type: DmDraftTriggerType
    created_at: datetime
    updated_at: datetime


class DmDraftPublishResult(ApiSchema):
    draft: DmDraftView
    message: MessageView
