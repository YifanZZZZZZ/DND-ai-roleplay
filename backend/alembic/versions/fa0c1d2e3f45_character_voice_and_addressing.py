"""add character voice samples and message addressing

Revision ID: fa0c1d2e3f45
Revises: f9b0c1d2e3f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fa0c1d2e3f45"
down_revision: str | None = "f9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("voice_samples", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "messages",
        sa.Column("addressed_character_ids", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("messages", "addressed_character_ids")
    op.drop_column("characters", "voice_samples")
