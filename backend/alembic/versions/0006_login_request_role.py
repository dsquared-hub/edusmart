"""Отдельный вход для ментора: запрос входа через бота помнит, с какой страницы он начат.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("login_requests", sa.Column("as_role", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("login_requests", "as_role")
