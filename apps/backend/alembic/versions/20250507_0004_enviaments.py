"""enviaments

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "enviaments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("alumne_id", sa.Integer(), nullable=True),
        sa.Column("destinatari_email", sa.String(150), nullable=False),
        sa.Column(
            "tipus",
            sa.Enum(
                "butlleti", "comunicat", "recordatori", "credencials",
                name="tipusenviament", native_enum=False, length=20,
            ),
            nullable=False,
        ),
        sa.Column("assumpte", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("adjunt_filename", sa.String(255), nullable=True),
        sa.Column(
            "estat",
            sa.Enum(
                "queued", "enviat", "obert", "rebotat", "error",
                name="estatenviament", native_enum=False, length=20,
            ),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("error_msg", sa.String(500), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("avaluacio_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["alumne_id"], ["alumnes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["avaluacio_id"], ["avaluacions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_enviaments_estat", "enviaments", ["estat"])
    op.create_index("ix_enviaments_alumne", "enviaments", ["alumne_id"])
    op.create_index("ix_enviaments_aval", "enviaments", ["avaluacio_id"])
    op.create_index("ix_enviaments_queued", "enviaments", ["queued_at"])


def downgrade() -> None:
    op.drop_index("ix_enviaments_queued", table_name="enviaments")
    op.drop_index("ix_enviaments_aval", table_name="enviaments")
    op.drop_index("ix_enviaments_alumne", table_name="enviaments")
    op.drop_index("ix_enviaments_estat", table_name="enviaments")
    op.drop_table("enviaments")
