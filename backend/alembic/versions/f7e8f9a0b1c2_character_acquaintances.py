"""add global character acquaintances"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7e8f9a0b1c2"
down_revision: str | None = "f6d7e8f9a0b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_acquaintances",
        sa.Column(
            "character_a_id",
            sa.String(36),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "character_b_id",
            sa.String(36),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "met_campaign_id",
            sa.String(36),
            sa.ForeignKey("campaigns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "character_a_id < character_b_id",
            name="ordered_character_pair",
        ),
    )
    op.create_index(
        "ix_character_acquaintances_met_campaign_id",
        "character_acquaintances",
        ["met_campaign_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_character_acquaintances_met_campaign_id",
        table_name="character_acquaintances",
    )
    op.drop_table("character_acquaintances")
