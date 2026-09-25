"""Модуль 4: программа (предметы и темы), банк вопросов, ответы, вечерний тест,
Exam Readiness Score, задания; заморозки серии и время напоминания у ученика.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "curriculum_subjects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("name_uz", sa.String(120), nullable=False),
        sa.Column("name_ru", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_curriculum_subjects"),
        sa.UniqueConstraint("code", "grade", name="uq_curriculum_subjects_code"),
    )
    op.create_table(
        "curriculum_topics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("grade", sa.SmallInteger(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("name_uz", sa.String(255), nullable=False),
        sa.Column("name_ru", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["curriculum_subjects.id"],
            name="fk_curriculum_topics_subject_id_curriculum_subjects", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_curriculum_topics"),
    )
    op.create_index("ix_curriculum_topics_subject_id", "curriculum_topics", ["subject_id"])

    op.create_table(
        "question_bank",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("options", JSONType, nullable=False),
        sa.Column("correct", sa.SmallInteger(), nullable=False),
        sa.Column("explanation", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["curriculum_topics.id"], name="fk_question_bank_topic_id_curriculum_topics", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_question_bank"),
    )
    op.create_index("ix_question_bank_topic_difficulty", "question_bank", ["topic_id", "difficulty", "lang"])

    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("time_ms", sa.Integer(), nullable=False),
        sa.Column("is_review", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.user_id"], name="fk_attempts_student_id_students", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["curriculum_topics.id"], name="fk_attempts_topic_id_curriculum_topics", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["question_bank.id"], name="fk_attempts_question_id_question_bank", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_attempts"),
    )
    op.create_index("ix_attempts_student_topic", "attempts", ["student_id", "topic_id"])
    op.create_index("ix_attempts_student_created", "attempts", ["student_id", "created_at"])

    op.create_table(
        "daily_tests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("topic_ids", JSONType, nullable=False),
        sa.Column("slots", JSONType, nullable=False),
        sa.Column("current", sa.SmallInteger(), nullable=False),
        sa.Column("difficulty", sa.SmallInteger(), nullable=False),
        sa.Column("retry", sa.Boolean(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("corrected", sa.SmallInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.user_id"], name="fk_daily_tests_student_id_students", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_daily_tests"),
        sa.UniqueConstraint("student_id", "date", name="uq_daily_tests_student_id"),
    )
    op.create_index("ix_daily_tests_student_id", "daily_tests", ["student_id"])

    op.create_table(
        "readiness_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=True),
        sa.Column("components", JSONType, nullable=False),
        sa.Column("calculated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.user_id"], name="fk_readiness_scores_student_id_students", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["curriculum_subjects.id"], name="fk_readiness_scores_subject_id_curriculum_subjects", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_readiness_scores"),
    )
    op.create_index("ix_readiness_student_subject", "readiness_scores", ["student_id", "subject_id", "calculated_at"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_user_id", sa.BigInteger(), nullable=False),
        sa.Column("student_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], name="fk_assignments_from_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.user_id"], name="fk_assignments_student_id_students", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["curriculum_topics.id"], name="fk_assignments_topic_id_curriculum_topics", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_assignments"),
    )
    op.create_index("ix_assignments_from_user_id", "assignments", ["from_user_id"])
    op.create_index("ix_assignments_student_id", "assignments", ["student_id"])

    # Существующие ученики получают значения по умолчанию
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("freeze_week", sa.String(10), nullable=True))
        batch.add_column(sa.Column("freezes_used", sa.SmallInteger(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("evening_time", sa.String(5), nullable=False, server_default="19:00"))
        batch.add_column(sa.Column("last_reminded_on", sa.Date(), nullable=True))

    with op.batch_alter_table("topics") as batch:
        batch.add_column(sa.Column("curriculum_topic_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_topics_curriculum_topic_id_curriculum_topics", "curriculum_topics",
            ["curriculum_topic_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index("ix_topics_curriculum_topic_id", ["curriculum_topic_id"])


def downgrade() -> None:
    with op.batch_alter_table("topics") as batch:
        batch.drop_index("ix_topics_curriculum_topic_id")
        batch.drop_constraint("fk_topics_curriculum_topic_id_curriculum_topics", type_="foreignkey")
        batch.drop_column("curriculum_topic_id")
    with op.batch_alter_table("students") as batch:
        for column in ("last_reminded_on", "evening_time", "freezes_used", "freeze_week"):
            batch.drop_column(column)
    for table, indexes in (
        ("assignments", ["ix_assignments_student_id", "ix_assignments_from_user_id"]),
        ("readiness_scores", ["ix_readiness_student_subject"]),
        ("daily_tests", ["ix_daily_tests_student_id"]),
        ("attempts", ["ix_attempts_student_created", "ix_attempts_student_topic"]),
        ("question_bank", ["ix_question_bank_topic_difficulty"]),
        ("curriculum_topics", ["ix_curriculum_topics_subject_id"]),
    ):
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
    op.drop_table("curriculum_subjects")
