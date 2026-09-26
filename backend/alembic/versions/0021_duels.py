"""PvP-дуэли учеников.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "duels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=8), nullable=False, unique=True),
        sa.Column("creator_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("opponent_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("lang", sa.String(length=5), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("questions", JSONType, nullable=False),
        sa.Column("results", JSONType, nullable=False),
        sa.Column("winner_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_duels_creator_id", "duels", ["creator_id"])
    op.create_index("ix_duels_opponent_id", "duels", ["opponent_id"])


def downgrade() -> None:
    op.drop_index("ix_duels_opponent_id", table_name="duels")
    op.drop_index("ix_duels_creator_id", table_name="duels")
    op.drop_table("duels")
