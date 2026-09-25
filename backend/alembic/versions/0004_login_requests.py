"""Вход на сайт через бота: запросы входа с подтверждением в Telegram.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("match_code", sa.SmallInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_login_requests_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_requests"),
        sa.UniqueConstraint("token_hash", name="uq_login_requests_token_hash"),
    )
    op.create_index("ix_login_requests_expires_at", "login_requests", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_login_requests_expires_at", table_name="login_requests")
    op.drop_table("login_requests")
