"""Сократовский тьютор: диалоги ученика с репетитором.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "tutor_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("messages", JSONType, nullable=False),
        sa.Column("points", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tutor_sessions_student_id", "tutor_sessions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_tutor_sessions_student_id", table_name="tutor_sessions")
    op.drop_table("tutor_sessions")
