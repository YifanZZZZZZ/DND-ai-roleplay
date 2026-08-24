"""add DM draft visibility and recipients

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaign_dm_drafts",
        sa.Column("audience", sa.String(20), nullable=False, server_default="PUBLIC"),
    )
    op.add_column(
        "campaign_dm_drafts",
        sa.Column("recipient_character_ids", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("campaign_dm_drafts", "recipient_character_ids")
    op.drop_column("campaign_dm_drafts", "audience")
