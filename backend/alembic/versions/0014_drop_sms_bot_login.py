"""Убраны вход по SMS и вход на сайт через бота: таблицы кодов и запросов входа.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_sms_codes_phone", table_name="sms_codes")
    op.drop_table("sms_codes")
    op.drop_index("ix_login_requests_expires_at", table_name="login_requests")
    op.drop_table("login_requests")


def downgrade() -> None:
    op.create_table(
        "login_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("match_code", sa.SmallInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("as_role", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_login_requests_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_requests"),
        sa.UniqueConstraint("token_hash", name="uq_login_requests_token_hash"),
    )
    op.create_index("ix_login_requests_expires_at", "login_requests", ["expires_at"])
    op.create_table(
        "sms_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sms_codes"),
    )
    op.create_index("ix_sms_codes_phone", "sms_codes", ["phone"])
