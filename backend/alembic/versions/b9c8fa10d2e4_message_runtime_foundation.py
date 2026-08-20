"""add message and agent run foundation

Revision ID: b9c8fa10d2e4
Revises: 7bf760e5fb25
Create Date: 2026-08-20 02:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c8fa10d2e4"
down_revision: str | Sequence[str] | None = "7bf760e5fb25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column(
            "sender_type",
            sa.Enum("DM", "CHARACTER", "SYSTEM", name="message_sender_type", native_enum=False),
            nullable=False,
        ),
        sa.Column("sender_character_id", sa.String(length=36), nullable=True),
        sa.Column(
            "kind",
            sa.Enum("IN_GAME", "OOC", "SYSTEM", name="message_kind", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "audience",
            sa.Enum("PUBLIC", "PRIVATE", "DM_ONLY", name="message_audience", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("client_request_id", sa.String(length=36), nullable=True),
        sa.Column("origin_agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence_no > 0", name=op.f("ck_messages_positive_sequence_no")),
        sa.CheckConstraint(
            "(sender_type = 'CHARACTER' AND sender_character_id IS NOT NULL) "
            "OR (sender_type != 'CHARACTER' AND sender_character_id IS NULL)",
            name=op.f("ck_messages_valid_sender"),
        ),
        sa.ForeignKeyConstraint(
            ["sender_character_id"],
            ["characters.id"],
            name=op.f("fk_messages_sender_character_id_characters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_messages_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint("client_request_id", name=op.f("uq_messages_client_request_id")),
    )
    op.create_index(
        "ux_messages_session_sequence", "messages", ["session_id", "sequence_no"], unique=True
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_message_id", sa.String(length=36), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "CANCELLED",
                "FAILED",
                name="agent_run_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "stop_reason",
            sa.Enum(
                "PUBLISHED",
                "ALL_SILENT",
                "WAITING_FOR_DM",
                "LIMIT_REACHED",
                "STALE",
                "DM_STOP",
                "DM_PREEMPTED",
                "ERROR",
                name="agent_run_stop_reason",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("selected_character_id", sa.String(length=36), nullable=True),
        sa.Column("published_message_id", sa.String(length=36), nullable=True),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("response_count", sa.Integer(), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "eligible_count >= 0", name=op.f("ck_agent_runs_non_negative_eligible_count")
        ),
        sa.CheckConstraint("generation >= 0", name=op.f("ck_agent_runs_non_negative_generation")),
        sa.CheckConstraint(
            "response_count >= 0", name=op.f("ck_agent_runs_non_negative_response_count")
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_agent_runs_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_agent_runs_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_message_id"],
            ["messages.id"],
            name=op.f("fk_agent_runs_trigger_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(op.f("ix_agent_runs_campaign_id"), "agent_runs", ["campaign_id"], unique=False)
    op.create_index(op.f("ix_agent_runs_session_id"), "agent_runs", ["session_id"], unique=False)
    op.create_index(
        op.f("ix_agent_runs_trigger_message_id"),
        "agent_runs",
        ["trigger_message_id"],
        unique=False,
    )
    op.create_table(
        "message_recipients",
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_message_recipients_character_id_characters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_recipients_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("message_id", "character_id", name=op.f("pk_message_recipients")),
    )
    op.create_index(
        "idx_message_recipients_character_message",
        "message_recipients",
        ["character_id", "message_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_message_recipients_character_message", table_name="message_recipients")
    op.drop_table("message_recipients")
    op.drop_index(op.f("ix_agent_runs_trigger_message_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_session_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_campaign_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ux_messages_session_sequence", table_name="messages")
    op.drop_table("messages")
