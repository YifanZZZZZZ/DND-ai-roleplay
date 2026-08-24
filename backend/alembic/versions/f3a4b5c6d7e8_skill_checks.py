"""add immutable skill check records

Revision ID: f3a4b5c6d7e8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-22 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "f2a3b4c5d6e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_checks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("skill", sa.String(length=40), nullable=False),
        sa.Column("modifier_snapshot", sa.Integer(), nullable=False),
        sa.Column(
            "roll_mode",
            sa.Enum("NORMAL", "ADVANTAGE", "DISADVANTAGE", name="roll_mode", native_enum=False),
            nullable=False,
        ),
        sa.Column("die_one", sa.Integer(), nullable=False),
        sa.Column("die_two", sa.Integer(), nullable=True),
        sa.Column("selected_die", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("dc", sa.Integer(), nullable=True),
        sa.Column(
            "system_outcome",
            sa.Enum(
                "PASS", "FAIL", "UNRESOLVED",
                name="skill_check_system_outcome", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "dm_adjudication",
            sa.Enum(
                "SUCCESS", "FAILURE", "PARTIAL_SUCCESS",
                name="skill_check_dm_adjudication", native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("client_request_id", sa.String(length=36), nullable=False),
        sa.Column(
            "status",
            sa.Enum("VALID", "VOID", name="skill_check_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("void_reason", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("die_one BETWEEN 1 AND 20", name="skill_check_die_one_range"),
        sa.CheckConstraint(
            "die_two IS NULL OR die_two BETWEEN 1 AND 20", name="skill_check_die_two_range"
        ),
        sa.CheckConstraint("selected_die BETWEEN 1 AND 20", name="skill_check_selected_range"),
        sa.CheckConstraint("dc IS NULL OR dc >= 0", name="non_negative_skill_check_dc"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_request_id"),
    )
    op.create_index("ix_skill_checks_campaign_id", "skill_checks", ["campaign_id"])
    op.create_index("ix_skill_checks_session_id", "skill_checks", ["session_id"])
    op.create_index("ix_skill_checks_character_id", "skill_checks", ["character_id"])


def downgrade() -> None:
    op.drop_index("ix_skill_checks_character_id", table_name="skill_checks")
    op.drop_index("ix_skill_checks_session_id", table_name="skill_checks")
    op.drop_index("ix_skill_checks_campaign_id", table_name="skill_checks")
    op.drop_table("skill_checks")
