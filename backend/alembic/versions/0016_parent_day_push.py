"""Дневное уведомление родителю: отметка «сегодня уже отправлено».

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("parent_day_pushed_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("students") as batch:
        batch.drop_column("parent_day_pushed_on")
