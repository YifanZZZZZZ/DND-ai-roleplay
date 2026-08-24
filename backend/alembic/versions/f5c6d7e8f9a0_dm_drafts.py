"""add manual AI DM drafts"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5c6d7e8f9a0"
down_revision: str | None = "f4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_dm_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.String(36),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_skill_check_id",
            sa.String(36),
            sa.ForeignKey("skill_checks.id", ondelete="SET NULL"),
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT", "PUBLISHED", "DISCARDED", name="dm_draft_status", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_campaign_dm_drafts_campaign_id", "campaign_dm_drafts", ["campaign_id"])
    op.create_index("ix_campaign_dm_drafts_session_id", "campaign_dm_drafts", ["session_id"])


def downgrade() -> None:
    op.drop_table("campaign_dm_drafts")
