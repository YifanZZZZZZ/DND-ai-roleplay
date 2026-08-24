"""add campaign NPC cards

Revision ID: fb1d2e3f4567
Revises: fa0c1d2e3f45
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fb1d2e3f4567"
down_revision: str | None = "fa0c1d2e3f45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT_COLUMNS = (
    "role",
    "personality",
    "ideal",
    "bond",
    "flaw",
    "knows",
    "wants",
    "voice",
)


def upgrade() -> None:
    op.create_table(
        "campaign_npcs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "campaign_id",
            sa.String(36),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        *(
            sa.Column(column, sa.Text(), nullable=False, server_default="")
            for column in _TEXT_COLUMNS
        ),
        sa.Column("source", sa.String(10), nullable=False, server_default="AUTO"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "campaign_dm_drafts",
        sa.Column("improvised_notes", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index(
        "ux_campaign_npcs_campaign_name",
        "campaign_npcs",
        ["campaign_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_campaign_npcs_campaign_name", table_name="campaign_npcs")
    op.drop_column("campaign_dm_drafts", "improvised_notes")
    op.drop_table("campaign_npcs")
