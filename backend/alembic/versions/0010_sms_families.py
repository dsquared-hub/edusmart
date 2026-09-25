"""Модуль 4: вход по номеру телефона с SMS-кодом и семейный аккаунт.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(16), nullable=True))
        batch.create_unique_constraint("uq_users_phone", ["phone"])

    op.create_table(
        "sms_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("phone", sa.String(16), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sms_codes"),
    )
    op.create_index("ix_sms_codes_phone", "sms_codes", ["phone"])

    op.create_table(
        "families",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_families"),
    )
    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("member_role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], name="fk_family_members_family_id_families", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_family_members_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_family_members"),
        sa.UniqueConstraint("family_id", "user_id", name="uq_family_members_family_id"),
    )
    op.create_index("ix_family_members_family_id", "family_members", ["family_id"])
    op.create_index("ix_family_members_user_id", "family_members", ["user_id"])
    op.create_table(
        "family_invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("family_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_by", sa.BigInteger(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["family_id"], ["families.id"], name="fk_family_invites_family_id_families", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_family_invites_created_by_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], name="fk_family_invites_used_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_family_invites"),
        sa.UniqueConstraint("code", name="uq_family_invites_code"),
    )
    op.create_index("ix_family_invites_family_id", "family_invites", ["family_id"])


def downgrade() -> None:
    op.drop_index("ix_family_invites_family_id", table_name="family_invites")
    op.drop_table("family_invites")
    op.drop_index("ix_family_members_user_id", table_name="family_members")
    op.drop_index("ix_family_members_family_id", table_name="family_members")
    op.drop_table("family_members")
    op.drop_table("families")
    op.drop_index("ix_sms_codes_phone", table_name="sms_codes")
    op.drop_table("sms_codes")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_phone", type_="unique")
        batch.drop_column("phone")
