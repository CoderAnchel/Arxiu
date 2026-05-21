"""app_settings — runtime configuration (SMTP, centre branding, etc.)

A single-row table; the admin edits it from the UI. The SMTP password is
stored encrypted (Fernet) so it never lives in plaintext on disk.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        # Single-row guard: enforced at app level. The PK is always 1.
        sa.Column("smtp_host", sa.String(255), nullable=True),
        sa.Column("smtp_port", sa.SmallInteger, nullable=True),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        # Fernet ciphertext (str). Decrypted on use; never returned to clients.
        sa.Column("smtp_password_encrypted", sa.Text, nullable=True),
        sa.Column("smtp_from_email", sa.String(255), nullable=True),
        sa.Column("smtp_from_name", sa.String(255), nullable=True),
        sa.Column(
            "smtp_use_tls", sa.Boolean, nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Column("updated_by_user_id", sa.Integer, nullable=True),
    )
    # Seed the single row so reads never have to handle a missing one.
    op.execute("INSERT INTO app_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("app_settings")
