"""add per-character behaviour rules and expression bans

Revision ID: fd3e4f567890
Revises: fc2e3f456789
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fd3e4f567890"
down_revision: str | None = "fc2e3f456789"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("behavior_rules", "expression_bans"):
        op.add_column(
            "characters", sa.Column(column, sa.Text(), nullable=False, server_default="")
        )


def downgrade() -> None:
    for column in ("expression_bans", "behavior_rules"):
        op.drop_column("characters", column)
