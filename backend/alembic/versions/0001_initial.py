"""Начальная схема: пользователи из любых источников, темы с состоянием, очередь событий.

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

JSONType = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", BigIntPK, autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(16), nullable=True),
        sa.Column("login", sa.String(32), nullable=True),
        sa.Column("access_code_hash", sa.String(255), nullable=True),
        sa.Column("code_issued_by", sa.BigInteger(), nullable=True),
        sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("theme", sa.String(16), nullable=False, server_default="sun"),
        sa.Column("high_contrast", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dyslexia_font", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lang", sa.String(5), nullable=False, server_default="ru"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["code_issued_by"], ["users.id"],
            name="fk_users_code_issued_by_users", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
        sa.UniqueConstraint("login", name="uq_users_login"),
    )

    op.create_table(
        "students",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("streak", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_active_on", sa.Date(), nullable=True),
        sa.Column("family_code", sa.String(6), nullable=False),
        sa.Column("consent_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_students_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_students"),
        sa.UniqueConstraint("family_code", name="uq_students_family_code"),
    )

    for table, owner in (("parent_links", "parent_user_id"), ("teacher_links", "teacher_user_id")):
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(owner, sa.BigInteger(), nullable=False),
            sa.Column("student_user_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                [owner], ["users.id"], name=f"fk_{table}_{owner}_users", ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["student_user_id"], ["students.user_id"],
                name=f"fk_{table}_student_user_id_students", ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            sa.UniqueConstraint(owner, "student_user_id", name=f"uq_{table}_{owner}"),
        )
        op.create_index(f"ix_{table}_{owner}", table, [owner])
        op.create_index(f"ix_{table}_student_user_id", table, ["student_user_id"])

    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(32), nullable=True),
        sa.Column("grade", sa.SmallInteger(), nullable=True),
        sa.Column("source", sa.String(8), nullable=False, server_default="bot"),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column("steps", JSONType, nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("points_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("practice", JSONType, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["student_user_id"], ["students.user_id"],
            name="fk_topics_student_user_id_students", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
    )
    op.create_index("ix_topics_student_user_id", "topics", ["student_user_id"])
    op.create_index("ix_topics_student_status", "topics", ["student_user_id", "status"])

    op.create_table(
        "step_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_step_attempts_topic_id_topics", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_step_attempts"),
    )
    op.create_index("ix_step_attempts_topic_id", "step_attempts", ["topic_id"])

    op.create_table(
        "daily_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("explanations", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_daily_usage_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_daily_usage"),
        sa.UniqueConstraint("user_id", "date", name="uq_daily_usage_user_id"),
    )
    op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"])

    op.create_table(
        "activity_days",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_activity_days_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_activity_days"),
        sa.UniqueConstraint("user_id", "date", name="uq_activity_days_user_id"),
    )
    op.create_index("ix_activity_days_user_id", "activity_days", ["user_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("payload", JSONType, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
    )
    op.create_index("ix_events_processed_at", "events", ["processed_at"])


def downgrade() -> None:
    for table in (
        "events",
        "activity_days",
        "daily_usage",
        "step_attempts",
        "topics",
        "teacher_links",
        "parent_links",
        "students",
        "users",
    ):
        op.drop_table(table)
