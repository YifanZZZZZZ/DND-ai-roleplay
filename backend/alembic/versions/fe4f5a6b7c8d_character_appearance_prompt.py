"""add character appearance prompt

Revision ID: fe4f5a6b7c8d
Revises: fd3e4f567890
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fe4f5a6b7c8d"
down_revision: str | None = "fd3e4f567890"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("appearance_prompt", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("characters", "appearance_prompt")
