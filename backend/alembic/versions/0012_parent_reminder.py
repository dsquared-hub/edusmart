"""Мягкое напоминание родителю о вечернем тесте; напоминания не позже 20:00.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("parent_reminded_on", sa.Date(), nullable=True))
    # Раньше можно было выбрать до 21:59 — это слишком поздно для ребёнка
    op.execute("UPDATE students SET evening_time = '20:00' WHERE evening_time > '20:00'")


def downgrade() -> None:
    with op.batch_alter_table("students") as batch:
        batch.drop_column("parent_reminded_on")
