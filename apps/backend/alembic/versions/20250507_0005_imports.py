"""imports

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tipus",
            sa.Enum("alumnes", "matricules", "notes",
                    name="tipusimport", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("fitxer_nom", sa.String(255), nullable=True),
        sa.Column("fitxer_path", sa.String(500), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ok", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("log", sa.JSON(), nullable=True),
        sa.Column(
            "estat",
            sa.Enum(
                "pending", "processing", "completed", "failed",
                name="estatimport", native_enum=False, length=20,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_imports_user_created", "imports", ["user_id", "created_at"])
    op.create_index("ix_imports_estat", "imports", ["estat"])


def downgrade() -> None:
    op.drop_index("ix_imports_estat", table_name="imports")
    op.drop_index("ix_imports_user_created", table_name="imports")
    op.drop_table("imports")
