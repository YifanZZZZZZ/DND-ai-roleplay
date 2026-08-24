"""add campaign dm guide and scene notes"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b5c6d7e8f9"
down_revision: str | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("campaigns")}
    if "dm_guide" not in existing:
        op.add_column(
            "campaigns", sa.Column("dm_guide", sa.Text(), nullable=False, server_default="")
        )
    if "scene_notes" not in existing:
        op.add_column(
            "campaigns", sa.Column("scene_notes", sa.Text(), nullable=False, server_default="")
        )


def downgrade() -> None:
    op.drop_column("campaigns", "scene_notes")
    op.drop_column("campaigns", "dm_guide")
