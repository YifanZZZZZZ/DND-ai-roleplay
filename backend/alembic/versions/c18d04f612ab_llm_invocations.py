"""add LLM invocation audit records

Revision ID: c18d04f612ab
Revises: b9c8fa10d2e4
Create Date: 2026-08-20 03:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c18d04f612ab"
down_revision: str | Sequence[str] | None = "b9c8fa10d2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_invocations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("agent_run_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum("CHARACTER", name="llm_purpose", native_enum=False),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="llm_invocation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name=op.f("ck_llm_invocations_non_negative_duration_ms"),
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name=op.f("ck_llm_invocations_non_negative_input_tokens"),
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name=op.f("ck_llm_invocations_non_negative_output_tokens"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_llm_invocations_agent_run_id_agent_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_llm_invocations_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["character_id"],
            ["characters.id"],
            name=op.f("fk_llm_invocations_character_id_characters"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["sessions.id"],
            name=op.f("fk_llm_invocations_session_id_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_invocations")),
    )
    op.create_index(
        op.f("ix_llm_invocations_agent_run_id"), "llm_invocations", ["agent_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_llm_invocations_campaign_id"), "llm_invocations", ["campaign_id"], unique=False
    )
    op.create_index(
        op.f("ix_llm_invocations_character_id"), "llm_invocations", ["character_id"], unique=False
    )
    op.create_index(
        op.f("ix_llm_invocations_session_id"), "llm_invocations", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_invocations_session_id"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_character_id"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_campaign_id"), table_name="llm_invocations")
    op.drop_index(op.f("ix_llm_invocations_agent_run_id"), table_name="llm_invocations")
    op.drop_table("llm_invocations")
