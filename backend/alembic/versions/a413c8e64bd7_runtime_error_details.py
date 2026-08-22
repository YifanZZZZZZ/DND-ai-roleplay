"""add runtime and invocation error details

Revision ID: a413c8e64bd7
Revises: e82c91a4f7bd
Create Date: 2026-08-22 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a413c8e64bd7"
down_revision: str | Sequence[str] | None = "e82c91a4f7bd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_runtimes") as batch:
        batch.add_column(sa.Column("last_error_code", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("last_error_message", sa.Text(), nullable=True))
    with op.batch_alter_table("llm_invocations") as batch:
        batch.add_column(sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("llm_invocations") as batch:
        batch.drop_column("error_message")
    with op.batch_alter_table("session_runtimes") as batch:
        batch.drop_column("last_error_message")
        batch.drop_column("last_error_code")
