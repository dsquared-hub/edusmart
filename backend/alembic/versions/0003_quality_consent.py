"""Качество и соответствие: журнал согласий, жалобы на ошибки, отзыв токенов,
счётчик упрощений, версия политики в согласии.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    with op.batch_alter_table("students") as batch:
        batch.add_column(sa.Column("consent_version", sa.String(32), nullable=True))
    with op.batch_alter_table("daily_usage") as batch:
        batch.add_column(sa.Column("simplifications", sa.Integer(), nullable=False, server_default="0"))

    # Согласия, данные до появления версий политики, помечаем как «legacy»:
    # при текущей версии политики родитель подтвердит согласие заново.
    op.execute("UPDATE students SET consent_version = 'legacy' WHERE consent_confirmed")

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_user_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("channel", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_consent_records"),
    )
    op.create_index("ix_consent_records_parent_user_id", "consent_records", ["parent_user_id"])
    op.create_index("ix_consent_records_student_user_id", "consent_records", ["student_user_id"])

    op.create_table(
        "content_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("reporter_user_id", sa.BigInteger(), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name="fk_content_reports_topic_id_topics", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"], ["users.id"],
            name="fk_content_reports_reporter_user_id_users", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_content_reports"),
    )
    op.create_index("ix_content_reports_topic_id", "content_reports", ["topic_id"])
    op.create_index("ix_content_reports_reporter_user_id", "content_reports", ["reporter_user_id"])
    op.create_index("ix_content_reports_status", "content_reports", ["status"])


def downgrade() -> None:
    op.drop_table("content_reports")
    op.drop_table("consent_records")
    with op.batch_alter_table("daily_usage") as batch:
        batch.drop_column("simplifications")
    with op.batch_alter_table("students") as batch:
        batch.drop_column("consent_version")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("token_version")
