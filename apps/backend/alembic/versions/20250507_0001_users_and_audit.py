"""users + audit_logs

Revision ID: 0001
Revises:
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dni", sa.String(15), nullable=False),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("cognoms", sa.String(150), nullable=False),
        sa.Column("departament", sa.String(100), nullable=True),
        sa.Column(
            "role",
            sa.Enum("admin", "professor", name="userrole", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("password_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_set_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("oauth_subject", sa.String(255), nullable=True),
        sa.Column("mfa_secret", sa.String(64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by_user_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("dni", name="uq_users_dni"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("oauth_subject", name="uq_users_oauth_subject"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    # Self-referencing FK created after table exists to avoid circular create-time issues
    op.create_foreign_key(
        "fk_users_password_set_by",
        "users",
        "users",
        ["password_set_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index("ix_users_dni", "users", ["dni"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role_active", "users", ["role", "active"])

    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL", name="fk_audit_user"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_entity", "audit_logs", ["entity", "entity_id"])
    op.create_index("ix_audit_user_created", "audit_logs", ["user_id", "created_at"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_action", table_name="audit_logs")
    op.drop_index("ix_audit_user_created", table_name="audit_logs")
    op.drop_index("ix_audit_entity", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_users_role_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_dni", table_name="users")
    op.drop_constraint("fk_users_password_set_by", "users", type_="foreignkey")
    op.drop_table("users")
