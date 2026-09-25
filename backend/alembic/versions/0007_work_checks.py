"""Academic Copilot: ИИ-проверка рукописных работ (пакеты и отдельные работы).

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "work_checks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("teacher_user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(32), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("task_text", sa.String(4000), nullable=True),
        sa.Column("answer_key", sa.String(4000), nullable=True),
        sa.Column("max_score", sa.SmallInteger(), nullable=False),
        sa.Column("training_consent", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["teacher_user_id"], ["users.id"], name="fk_work_checks_teacher_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_checks"),
    )
    op.create_index("ix_work_checks_teacher_user_id", "work_checks", ["teacher_user_id"])
    op.create_index("ix_work_checks_status", "work_checks", ["status"])

    op.create_table(
        "work_check_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("check_id", sa.Integer(), nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("recognized_text", sa.String(8000), nullable=True),
        sa.Column("ai_score", sa.SmallInteger(), nullable=True),
        sa.Column("ai_comment", sa.String(2000), nullable=True),
        sa.Column("ai_marks", JSONType, nullable=True),
        sa.Column("confidence", sa.SmallInteger(), nullable=True),
        sa.Column("neatness", sa.SmallInteger(), nullable=True),
        sa.Column("teacher_score", sa.SmallInteger(), nullable=True),
        sa.Column("teacher_comment", sa.String(2000), nullable=True),
        sa.Column("teacher_marks", JSONType, nullable=True),
        sa.Column("viewed_at", sa.DateTime(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["check_id"], ["work_checks.id"], name="fk_work_check_items_check_id_work_checks", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["students.user_id"],
            name="fk_work_check_items_student_user_id_students", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_work_check_items"),
    )
    op.create_index("ix_work_check_items_check_id", "work_check_items", ["check_id"])
    op.create_index("ix_work_check_items_student_user_id", "work_check_items", ["student_user_id"])
    op.create_index("ix_work_check_items_status_created", "work_check_items", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_work_check_items_status_created", table_name="work_check_items")
    op.drop_index("ix_work_check_items_student_user_id", table_name="work_check_items")
    op.drop_index("ix_work_check_items_check_id", table_name="work_check_items")
    op.drop_table("work_check_items")
    op.drop_index("ix_work_checks_status", table_name="work_checks")
    op.drop_index("ix_work_checks_teacher_user_id", table_name="work_checks")
    op.drop_table("work_checks")
