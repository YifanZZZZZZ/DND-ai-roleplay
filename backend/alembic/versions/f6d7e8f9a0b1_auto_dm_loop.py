"""add campaign module and automatic dm draft fields"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6d7e8f9a0b1"
down_revision: str | None = "f5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for name in ("module_content", "style_instructions", "opening_instructions"):
        op.add_column("campaigns", sa.Column(name, sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "campaigns",
        sa.Column("play_mode", sa.String(32), nullable=False, server_default="NARRATIVE"),
    )
    with op.batch_alter_table("campaign_dm_drafts") as batch:
        batch.alter_column("status", existing_type=sa.String(9), type_=sa.String(32))
        batch.alter_column("session_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("source_message_id", sa.String(36), nullable=True))
        batch.add_column(
            sa.Column("trigger_type", sa.String(32), nullable=False, server_default="MANUAL_ASSIST")
        )
        batch.add_column(sa.Column("prompt", sa.Text(), nullable=True))
    op.create_index(
        "ix_campaign_dm_drafts_source_message_id", "campaign_dm_drafts", ["source_message_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_dm_drafts_source_message_id", table_name="campaign_dm_drafts")
    with op.batch_alter_table("campaign_dm_drafts") as batch:
        batch.drop_column("prompt")
        batch.drop_column("trigger_type")
        batch.drop_column("source_message_id")
        batch.alter_column("status", existing_type=sa.String(32), type_=sa.String(9))
        batch.alter_column("session_id", existing_type=sa.String(36), nullable=False)
    op.drop_column("campaigns", "play_mode")
    op.drop_column("campaigns", "opening_instructions")
    op.drop_column("campaigns", "style_instructions")
    op.drop_column("campaigns", "module_content")
