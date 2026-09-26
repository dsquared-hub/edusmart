"""Stories для ученика: колоды карточек и прогресс ученика.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "story_decks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("author_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("lesson_materials.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=32), nullable=True),
        sa.Column("lang", sa.String(length=5), nullable=False),
        sa.Column("slides", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_story_decks_author_user_id", "story_decks", ["author_user_id"])
    op.create_index("ix_story_decks_material_id", "story_decks", ["material_id"])
    op.create_table(
        "story_views",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("deck_id", sa.Integer(), sa.ForeignKey("story_decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.BigInteger(), sa.ForeignKey("students.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("answers", JSONType, nullable=False),
        sa.Column("coins", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("deck_id", "student_id"),
    )
    op.create_index("ix_story_views_deck_id", "story_views", ["deck_id"])
    op.create_index("ix_story_views_student_id", "story_views", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_story_views_student_id", table_name="story_views")
    op.drop_index("ix_story_views_deck_id", table_name="story_views")
    op.drop_table("story_views")
    op.drop_index("ix_story_decks_material_id", table_name="story_decks")
    op.drop_index("ix_story_decks_author_user_id", table_name="story_decks")
    op.drop_table("story_decks")
