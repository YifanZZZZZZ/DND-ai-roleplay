from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.ids import new_id
from backend.app.db.base import Base, utc_now
from backend.app.domain.enums import (
    AgentRunStatus,
    AgentRunStopReason,
    CampaignLifecycleStatus,
    LlmInvocationStatus,
    LlmPurpose,
    MemoryOrigin,
    MessageAudience,
    MessageKind,
    MessageSenderType,
    ProfileStatus,
    RuntimeStatus,
    SessionStatus,
    SheetParseStatus,
    SummaryAudience,
    UpdatedBy,
)


def enum_column(enum_type: type[Any], name: str) -> Enum:
    return Enum(enum_type, name=name, native_enum=False, validate_strings=True)


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    roleplay_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_path: Mapped[str | None] = mapped_column(String(500))
    max_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    # Application-validated to avoid a circular SQLite DDL dependency with
    # character_sheet_versions. Sheet activation verifies ownership.
    active_sheet_version_id: Mapped[str | None] = mapped_column(String(36))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    sheet_versions: Mapped[list[CharacterSheetVersion]] = relationship(
        back_populates="character",
        cascade="all, delete-orphan",
        foreign_keys="CharacterSheetVersion.character_id",
    )
    profile: Mapped[CharacterProfile] = relationship(
        back_populates="character", cascade="all, delete-orphan", uselist=False
    )
    memberships: Mapped[list[CampaignMembership]] = relationship(back_populates="character")
    memories: Mapped[list[CharacterMemory]] = relationship(
        back_populates="character", cascade="all, delete-orphan"
    )

    __table_args__ = (CheckConstraint("max_hp > 0", name="positive_max_hp"),)


class CharacterSheetVersion(Base):
    __tablename__ = "character_sheet_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stored_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parse_status: Mapped[SheetParseStatus] = mapped_column(
        enum_column(SheetParseStatus, "sheet_parse_status"), nullable=False
    )
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    parsed_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    parse_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    character: Mapped[Character] = relationship(
        back_populates="sheet_versions", foreign_keys=[character_id]
    )


class CharacterProfile(Base):
    __tablename__ = "character_profiles"

    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ProfileStatus] = mapped_column(
        enum_column(ProfileStatus, "profile_status"), nullable=False, default=ProfileStatus.READY
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_by: Mapped[UpdatedBy] = mapped_column(
        enum_column(UpdatedBy, "updated_by"), nullable=False, default=UpdatedBy.DM
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    character: Mapped[Character] = relationship(back_populates="profile")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[CampaignLifecycleStatus] = mapped_column(
        enum_column(CampaignLifecycleStatus, "campaign_lifecycle_status"),
        nullable=False,
        default=CampaignLifecycleStatus.PREPARATION,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    memberships: Mapped[list[CampaignMembership]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[GameSession]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ux_campaign_single_active",
            "lifecycle_status",
            unique=True,
            sqlite_where=text("lifecycle_status = 'ACTIVE'"),
        ),
    )


class CampaignMembership(Base):
    __tablename__ = "campaign_memberships"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="RESTRICT"), primary_key=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    joined_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    joined_after_message_id: Mapped[str | None] = mapped_column(String(36))

    campaign: Mapped[Campaign] = relationship(back_populates="memberships")
    character: Mapped[Character] = relationship(back_populates="memberships")


class GameSession(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        enum_column(SessionStatus, "session_status"), nullable=False, default=SessionStatus.ACTIVE
    )
    next_sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    campaign: Mapped[Campaign] = relationship(back_populates="sessions")
    character_states: Mapped[list[SessionCharacterState]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    runtime: Mapped[SessionRuntime] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    llm_invocations: Mapped[list[LlmInvocation]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    summaries: Mapped[list[SessionSummary]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ux_session_single_active_per_campaign",
            "campaign_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        CheckConstraint("next_sequence_no > 0", name="positive_next_sequence_no"),
    )


class SessionCharacterState(Base):
    __tablename__ = "session_character_states"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="RESTRICT"), primary_key=True
    )
    current_hp: Mapped[int] = mapped_column(Integer, nullable=False)
    max_hp_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    session: Mapped[GameSession] = relationship(back_populates="character_states")
    character: Mapped[Character] = relationship()

    __table_args__ = (
        CheckConstraint("max_hp_snapshot > 0", name="positive_max_hp_snapshot"),
        CheckConstraint("current_hp >= 0", name="non_negative_current_hp"),
        CheckConstraint("current_hp <= max_hp_snapshot", name="current_hp_within_max"),
    )


class SessionRuntime(Base):
    __tablename__ = "session_runtimes"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[RuntimeStatus] = mapped_column(
        enum_column(RuntimeStatus, "runtime_status"), nullable=False, default=RuntimeStatus.IDLE
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_agent_run_id: Mapped[str | None] = mapped_column(String(36))
    last_trigger_message_id: Mapped[str | None] = mapped_column(String(36))
    waiting_message_id: Mapped[str | None] = mapped_column(String(36))
    waiting_request: Mapped[str | None] = mapped_column(Text)
    consecutive_ai_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    session: Mapped[GameSession] = relationship(back_populates="runtime")

    __table_args__ = (
        CheckConstraint("generation >= 0", name="non_negative_generation"),
        CheckConstraint(
            "consecutive_ai_messages >= 0 AND consecutive_ai_messages <= 12",
            name="valid_consecutive_ai_messages",
        ),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sender_type: Mapped[MessageSenderType] = mapped_column(
        enum_column(MessageSenderType, "message_sender_type"), nullable=False
    )
    sender_character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="RESTRICT")
    )
    kind: Mapped[MessageKind] = mapped_column(
        enum_column(MessageKind, "message_kind"), nullable=False
    )
    audience: Mapped[MessageAudience] = mapped_column(
        enum_column(MessageAudience, "message_audience"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    client_request_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    # Agent runs and messages point to each other. The link is application-validated
    # so SQLite migration order remains acyclic.
    origin_agent_run_id: Mapped[str | None] = mapped_column(String(36))
    supersedes_message_id: Mapped[str | None] = mapped_column(String(36))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_by_ooc_id: Mapped[str | None] = mapped_column(String(36))
    ooc_correction_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    session: Mapped[GameSession] = relationship(back_populates="messages")
    sender_character: Mapped[Character | None] = relationship(foreign_keys=[sender_character_id])
    recipients: Mapped[list[MessageRecipient]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("sequence_no > 0", name="positive_sequence_no"),
        CheckConstraint(
            "(sender_type = 'CHARACTER' AND sender_character_id IS NOT NULL) "
            "OR (sender_type != 'CHARACTER' AND sender_character_id IS NULL)",
            name="valid_sender",
        ),
        Index("ux_messages_session_sequence", "session_id", "sequence_no", unique=True),
    )


class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="RESTRICT"), primary_key=True
    )

    message: Mapped[Message] = relationship(back_populates="recipients")
    character: Mapped[Character] = relationship()

    __table_args__ = (
        Index("idx_message_recipients_character_message", "character_id", "message_id"),
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        enum_column(AgentRunStatus, "agent_run_status"),
        nullable=False,
        default=AgentRunStatus.PENDING,
    )
    stop_reason: Mapped[AgentRunStopReason | None] = mapped_column(
        enum_column(AgentRunStopReason, "agent_run_stop_reason")
    )
    selected_character_id: Mapped[str | None] = mapped_column(String(36))
    published_message_id: Mapped[str | None] = mapped_column(String(36))
    replacement_for_message_id: Mapped[str | None] = mapped_column(String(36))
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    random_seed: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[GameSession] = relationship(back_populates="agent_runs")

    __table_args__ = (
        CheckConstraint("generation >= 0", name="non_negative_generation"),
        CheckConstraint("eligible_count >= 0", name="non_negative_eligible_count"),
        CheckConstraint("response_count >= 0", name="non_negative_response_count"),
    )


class LlmInvocation(Base):
    __tablename__ = "llm_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    purpose: Mapped[LlmPurpose] = mapped_column(
        enum_column(LlmPurpose, "llm_purpose"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[LlmInvocationStatus] = mapped_column(
        enum_column(LlmInvocationStatus, "llm_invocation_status"),
        nullable=False,
        default=LlmInvocationStatus.RUNNING,
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[GameSession] = relationship(back_populates="llm_invocations")

    __table_args__ = (
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0", name="non_negative_input_tokens"
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0", name="non_negative_output_tokens"
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="non_negative_duration_ms"),
    )


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE")
    )
    audience: Mapped[SummaryAudience] = mapped_column(
        enum_column(SummaryAudience, "summary_audience"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    session: Mapped[GameSession] = relationship(back_populates="summaries")

    __table_args__ = (
        CheckConstraint(
            "(audience = 'DM' AND character_id IS NULL) "
            "OR (audience = 'CHARACTER' AND character_id IS NOT NULL)",
            name="valid_summary_audience",
        ),
        UniqueConstraint(
            "session_id",
            "audience",
            "character_id",
            name="ux_session_summaries_audience_character",
        ),
    )


class CharacterMemory(Base):
    __tablename__ = "character_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    character_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_campaign_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    source_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="SET NULL")
    )
    origin: Mapped[MemoryOrigin] = mapped_column(
        enum_column(MemoryOrigin, "memory_origin"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    character: Mapped[Character] = relationship(back_populates="memories")
