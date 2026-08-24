"""add fixed eighteen-skill modifier sets

Revision ID: f2a3b4c5d6e7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-22 12:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DEFAULT_MODIFIERS = (
    '{"athletics":0,"acrobatics":0,"sleight_of_hand":0,"stealth":0,'
    '"arcana":0,"history":0,"investigation":0,"nature":0,"religion":0,'
    '"animal_handling":0,"insight":0,"medicine":0,"perception":0,"survival":0,'
    '"deception":0,"intimidation":0,"performance":0,"persuasion":0}'
)


def upgrade() -> None:
    op.create_table(
        "character_skill_sets",
        sa.Column("character_id", sa.String(length=36), nullable=False),
        sa.Column("modifiers", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("character_id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO character_skill_sets "
            "(character_id, modifiers, revision, updated_at) "
            "SELECT id, :modifiers, 1, CURRENT_TIMESTAMP FROM characters"
        ).bindparams(modifiers=_DEFAULT_MODIFIERS)
    )


def downgrade() -> None:
    op.drop_table("character_skill_sets")
