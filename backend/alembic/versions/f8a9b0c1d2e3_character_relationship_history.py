"""add character relationship history

Revision ID: f8a9b0c1d2e3
Revises: f7e8f9a0b1c2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "f7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "character_acquaintances",
        sa.Column("relationship_history", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("character_acquaintances", "relationship_history")
