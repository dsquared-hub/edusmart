"""Academic Copilot: учебники, фрагменты для RAG и сгенерированные материалы уроков.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "textbooks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_teacher_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(32), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("license_note", sa.String(500), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("embed_model", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_teacher_id"], ["users.id"], name="fk_textbooks_owner_teacher_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_textbooks"),
    )
    op.create_index("ix_textbooks_owner_teacher_id", "textbooks", ["owner_teacher_id"])

    op.create_table(
        "textbook_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("textbook_id", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(4000), nullable=False),
        sa.Column("embedding", JSONType, nullable=False),
        sa.ForeignKeyConstraint(
            ["textbook_id"], ["textbooks.id"], name="fk_textbook_chunks_textbook_id_textbooks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_textbook_chunks"),
    )
    op.create_index("ix_textbook_chunks_textbook_id", "textbook_chunks", ["textbook_id"])

    op.create_table(
        "lesson_materials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("textbook_id", sa.Integer(), nullable=True),
        sa.Column("topic", sa.String(255), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("content", JSONType, nullable=False),
        sa.Column("sources", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["teacher_user_id"], ["users.id"], name="fk_lesson_materials_teacher_user_id_users", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["textbook_id"], ["textbooks.id"], name="fk_lesson_materials_textbook_id_textbooks", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_materials"),
    )
    op.create_index("ix_lesson_materials_teacher_user_id", "lesson_materials", ["teacher_user_id"])


def downgrade() -> None:
    op.drop_index("ix_lesson_materials_teacher_user_id", table_name="lesson_materials")
    op.drop_table("lesson_materials")
    op.drop_index("ix_textbook_chunks_textbook_id", table_name="textbook_chunks")
    op.drop_table("textbook_chunks")
    op.drop_index("ix_textbooks_owner_teacher_id", table_name="textbooks")
    op.drop_table("textbooks")
