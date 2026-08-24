"""add character narration notes and lower the AI chain cap

Revision ID: fc2e3f456789
Revises: fb1d2e3f4567
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fc2e3f456789"
down_revision: str | None = "fb1d2e3f4567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "characters",
        sa.Column("narration_notes", sa.Text(), nullable=False, server_default=""),
    )
    # Existing rows may hold a value above the new ceiling; clamp before the
    # tightened CHECK constraint is recreated.
    op.execute(
        "UPDATE session_runtimes SET consecutive_ai_messages = 5 "
        "WHERE consecutive_ai_messages > 5"
    )
    with op.batch_alter_table("session_runtimes") as batch:
        batch.drop_constraint("valid_consecutive_ai_messages", type_="check")
        batch.create_check_constraint(
            "valid_consecutive_ai_messages",
            "consecutive_ai_messages >= 0 AND consecutive_ai_messages <= 5",
        )


def downgrade() -> None:
    with op.batch_alter_table("session_runtimes") as batch:
        batch.drop_constraint("valid_consecutive_ai_messages", type_="check")
        batch.create_check_constraint(
            "valid_consecutive_ai_messages",
            "consecutive_ai_messages >= 0 AND consecutive_ai_messages <= 12",
        )
    op.drop_column("characters", "narration_notes")
