"""add OOC message revision links

Revision ID: d52f8b71e3ca
Revises: c18d04f612ab
Create Date: 2026-08-20 04:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d52f8b71e3ca"
down_revision: str | Sequence[str] | None = "c18d04f612ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("supersedes_message_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("invalidated_by_ooc_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("ooc_correction_note", sa.Text(), nullable=True))
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(
            sa.Column("replacement_for_message_id", sa.String(length=36), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_column("replacement_for_message_id")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("ooc_correction_note")
        batch.drop_column("invalidated_by_ooc_id")
        batch.drop_column("invalidated_at")
        batch.drop_column("supersedes_message_id")
