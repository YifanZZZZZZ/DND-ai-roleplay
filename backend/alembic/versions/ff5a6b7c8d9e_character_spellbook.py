"""add editable character spellbook

Revision ID: ff5a6b7c8d9e
Revises: fe4f5a6b7c8d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ff5a6b7c8d9e"
down_revision: str | None = "fe4f5a6b7c8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("spellbook", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("characters", "spellbook")
