"""IELTS AI Coach: задания (общие) и попытки учеников.

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "ielts_materials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ielts_materials_kind", "ielts_materials", ["kind"])
    op.create_table(
        "ielts_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("ielts_materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("answers", JSONType, nullable=False),
        sa.Column("result", JSONType, nullable=True),
        sa.Column("band", sa.Float(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ielts_attempts_student_id", "ielts_attempts", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_ielts_attempts_student_id", table_name="ielts_attempts")
    op.drop_table("ielts_attempts")
    op.drop_index("ix_ielts_materials_kind", table_name="ielts_materials")
    op.drop_table("ielts_materials")
