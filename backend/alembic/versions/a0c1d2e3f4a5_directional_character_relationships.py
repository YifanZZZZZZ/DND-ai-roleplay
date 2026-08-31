"""replace shared acquaintances with directional character relationships"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0c1d2e3f4a5"
down_revision: str | None = "ff5a6b7c8d9e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_relationships",
        sa.Column("owner_character_id", sa.String(length=36), nullable=False),
        sa.Column("target_character_id", sa.String(length=36), nullable=False),
        sa.Column("met_campaign_id", sa.String(length=36), nullable=True),
        sa.Column("current_view", sa.Text(), nullable=False, server_default=""),
        sa.Column("important_history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("last_processed_message_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "owner_character_id != target_character_id",
            name="relationship_distinct_characters",
        ),
        sa.ForeignKeyConstraint(
            ["last_processed_message_id"], ["messages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["met_campaign_id"], ["campaigns.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["owner_character_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_character_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("owner_character_id", "target_character_id"),
    )
    op.create_index(
        "ix_character_relationships_met_campaign_id",
        "character_relationships",
        ["met_campaign_id"],
    )
    op.execute(
        """
        INSERT INTO character_relationships (
            owner_character_id, target_character_id, met_campaign_id,
            current_view, important_history, created_at, updated_at
        )
        SELECT character_a_id, character_b_id, met_campaign_id,
               relationship_history, '[]', created_at, updated_at
        FROM character_acquaintances
        UNION ALL
        SELECT character_b_id, character_a_id, met_campaign_id,
               relationship_history, '[]', created_at, updated_at
        FROM character_acquaintances
        """
    )
    op.drop_index(
        "ix_character_acquaintances_met_campaign_id",
        table_name="character_acquaintances",
    )
    op.drop_table("character_acquaintances")


def downgrade() -> None:
    op.create_table(
        "character_acquaintances",
        sa.Column("character_a_id", sa.String(length=36), nullable=False),
        sa.Column("character_b_id", sa.String(length=36), nullable=False),
        sa.Column("met_campaign_id", sa.String(length=36), nullable=True),
        sa.Column("relationship_history", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("character_a_id < character_b_id", name="ordered_character_pair"),
        sa.ForeignKeyConstraint(
            ["met_campaign_id"], ["campaigns.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["character_a_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_b_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("character_a_id", "character_b_id"),
    )
    op.create_index(
        "ix_character_acquaintances_met_campaign_id",
        "character_acquaintances",
        ["met_campaign_id"],
    )
    op.execute(
        """
        INSERT INTO character_acquaintances (
            character_a_id, character_b_id, met_campaign_id,
            relationship_history, created_at, updated_at
        )
        SELECT owner_character_id, target_character_id, met_campaign_id,
               current_view, created_at, updated_at
        FROM character_relationships
        WHERE owner_character_id < target_character_id
        """
    )
    op.drop_index(
        "ix_character_relationships_met_campaign_id",
        table_name="character_relationships",
    )
    op.drop_table("character_relationships")
