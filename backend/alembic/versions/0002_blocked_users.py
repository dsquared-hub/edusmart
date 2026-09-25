"""Бан-лист владельца бота (перенесён из старого бота).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "blocked_users",
        sa.Column("telegram_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id", name="pk_blocked_users"),
    )


def downgrade() -> None:
    op.drop_table("blocked_users")
