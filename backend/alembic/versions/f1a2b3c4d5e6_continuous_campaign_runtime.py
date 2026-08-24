"""make campaign runtime one-to-one and add paused lifecycle

Revision ID: f1a2b3c4d5e6
Revises: e82c91a4f7bd
Create Date: 2026-08-22 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "a413c8e64bd7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Campaign history was intentionally cleared before this migration, so
    # the unconditional uniqueness rule cannot collide with legacy sessions.
    op.drop_index("ux_session_single_active_per_campaign", table_name="sessions")
    op.create_index(
        "ux_session_single_per_campaign",
        "sessions",
        ["campaign_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_session_single_per_campaign", table_name="sessions")
    op.create_index(
        "ux_session_single_active_per_campaign",
        "sessions",
        ["campaign_id"],
        unique=True,
        sqlite_where="status = 'ACTIVE'",
    )
