"""Персонаж и магазин: коины за очки, купленные вещи.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("coins", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("points_exchanged", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "student_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_code", sa.String(length=32), nullable=False),
        sa.Column("equipped", sa.Boolean(), nullable=False),
        sa.Column("bought_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "item_code"),
    )
    op.create_index("ix_student_items_user_id", "student_items", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_student_items_user_id", table_name="student_items")
    op.drop_table("student_items")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("points_exchanged")
        batch.drop_column("coins")
