"""add character memory and session summaries

Revision ID: e82c91a4f7bd
Revises: d52f8b71e3ca
Create Date: 2026-08-20 04:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e82c91a4f7bd"
down_revision: str | Sequence[str] | None = "d52f8b71e3ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_memories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("source_campaign_id", sa.String(length=36), nullable=True),
        sa.Column("source_session_id", sa.String(length=36), nullable=True),
        sa.Column(
            "origin",
            sa.Enum("DM", "AUTO", name="memory_origin", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_session_id"], ["sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_character_memories_character_id"), "character_memories", ["character_id"]
    )
    op.create_index(
        op.f("ix_character_memories_source_campaign_id"),
        "character_memories",
        ["source_campaign_id"],
    )
    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("character_id", sa.String(length=36), nullable=True),
        sa.Column(
            "audience",
            sa.Enum("DM", "CHARACTER", name="summary_audience", native_enum=False),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(audience = 'DM' AND character_id IS NULL) "
            "OR (audience = 'CHARACTER' AND character_id IS NOT NULL)",
            name="valid_summary_audience",
        ),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "audience",
            "character_id",
            name="ux_session_summaries_audience_character",
        ),
    )
    op.create_index(op.f("ix_session_summaries_session_id"), "session_summaries", ["session_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_session_summaries_session_id"), table_name="session_summaries")
    op.drop_table("session_summaries")
    op.drop_index(op.f("ix_character_memories_source_campaign_id"), table_name="character_memories")
    op.drop_index(op.f("ix_character_memories_character_id"), table_name="character_memories")
    op.drop_table("character_memories")
