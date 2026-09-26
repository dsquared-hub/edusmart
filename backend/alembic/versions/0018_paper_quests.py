"""Квесты Paper-to-Digital: задача в тетради, проверка фото, EduCoin ×2.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_quests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_index", sa.SmallInteger(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("answer", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("neatness", sa.SmallInteger(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("coins", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("passed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("student_id", "topic_id", "task_index"),
    )
    op.create_index("ix_paper_quests_student_id", "paper_quests", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_quests_student_id", table_name="paper_quests")
    op.drop_table("paper_quests")
