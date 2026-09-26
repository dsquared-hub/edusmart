"""ДТМ-симулятор: банк вопросов и варианты учеников.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "dtm_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subject", sa.String(length=32), nullable=False),
        sa.Column("section", sa.String(length=255), nullable=False),
        sa.Column("lang", sa.String(length=5), nullable=False),
        sa.Column("question", sa.String(length=1000), nullable=False),
        sa.Column("options", JSONType, nullable=False),
        sa.Column("correct", sa.SmallInteger(), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_dtm_questions_subject_lang", "dtm_questions", ["subject", "lang"])
    op.create_table(
        "dtm_tests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("spec1", sa.String(length=32), nullable=False),
        sa.Column("spec2", sa.String(length=32), nullable=False),
        sa.Column("lang", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("slots", JSONType, nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("deadline_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("results", JSONType, nullable=True),
    )
    op.create_index("ix_dtm_tests_student_id", "dtm_tests", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_dtm_tests_student_id", table_name="dtm_tests")
    op.drop_table("dtm_tests")
    op.drop_index("ix_dtm_questions_subject_lang", table_name="dtm_questions")
    op.drop_table("dtm_questions")
