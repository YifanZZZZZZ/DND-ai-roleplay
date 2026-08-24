from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from backend.app.api.schemas.base import ApiSchema
from backend.app.domain.enums import MessageAudience, MessageKind, MessageSenderType, RuntimeStatus


class DmMessageCreate(ApiSchema):
    content: str = Field(min_length=1, max_length=3000)
    audience: MessageAudience = MessageAudience.PUBLIC
    recipient_character_ids: list[str] = Field(default_factory=list, max_length=6)
    # Optional explicit addressing. Lets the DM point at characters with pronouns
    # ("你们两个先进去") without relying on name substring matching.
    addressed_character_ids: list[str] = Field(default_factory=list, max_length=6)
    client_request_id: UUID

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("消息内容不能为空。")
        return value


class OocCorrectionCreate(ApiSchema):
    target_message_id: str
    correction: str = Field(min_length=1, max_length=3000)
    replacement_content: str | None = Field(default=None, max_length=3000)
    client_request_id: UUID

    @field_validator("correction")
    @classmethod
    def reject_blank_correction(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("OOC 纠正不能为空。")
        return value


class MessageRecipientView(ApiSchema):
    character_id: str
    name: str


class MessageView(ApiSchema):
    id: str
    campaign_id: str
    sequence_no: int
    sender_type: MessageSenderType
    sender_character_id: str | None
    sender_name: str | None
    kind: MessageKind
    audience: MessageAudience
    content: str
    addressed_character_ids: list[str]
    is_ooc_corrected: bool
    ooc_correction_note: str | None
    recipients: list[MessageRecipientView]
    created_at: datetime


class RuntimeState(ApiSchema):
    status: RuntimeStatus
    generation: int
    active_agent_run_id: str | None
    waiting_request: str | None
    last_error_code: str | None
    last_error_message: str | None
    consecutive_ai_messages: int


class DmMessageCommandResult(ApiSchema):
    message: MessageView
    runtime: RuntimeState
