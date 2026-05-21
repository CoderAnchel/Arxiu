"""avaluacions + qualificacions_ra + qualificacions_modul

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "avaluacions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("curs_acad_id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("ordre", sa.SmallInteger(), nullable=False),
        sa.Column(
            "estat",
            sa.Enum(
                "oberta", "docent", "junta", "tancada",
                name="estatavaluacio", native_enum=False, length=20,
            ),
            nullable=False,
            server_default="oberta",
        ),
        sa.Column("data_inici", sa.Date(), nullable=True),
        sa.Column("data_tancament", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["curs_acad_id"], ["cursos_academics.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("curs_acad_id", "ordre", name="uq_avaluacio_curs_ordre"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_avaluacions_curs", "avaluacions", ["curs_acad_id"])

    op.create_table(
        "qualificacions_ra",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("matricula_id", sa.Integer(), nullable=False),
        sa.Column("ra_id", sa.Integer(), nullable=False),
        sa.Column("avaluacio_id", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Numeric(4, 2), nullable=True),
        sa.Column("comentari", sa.Text(), nullable=True),
        sa.Column("professor_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["matricula_id"], ["matricules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ra_id"], ["ras.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["avaluacio_id"], ["avaluacions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["professor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("matricula_id", "ra_id", "avaluacio_id", name="uq_qra_matr_ra_aval"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_qra_matricula", "qualificacions_ra", ["matricula_id"])
    op.create_index("ix_qra_ra", "qualificacions_ra", ["ra_id"])
    op.create_index("ix_qra_avaluacio", "qualificacions_ra", ["avaluacio_id"])
    op.create_index("ix_qra_aval_matr", "qualificacions_ra", ["avaluacio_id", "matricula_id"])

    op.create_table(
        "qualificacions_modul",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("matricula_id", sa.Integer(), nullable=False),
        sa.Column("modul_id", sa.Integer(), nullable=False),
        sa.Column("avaluacio_id", sa.Integer(), nullable=False),
        sa.Column("nota", sa.Numeric(4, 2), nullable=True),
        sa.Column("comentari", sa.Text(), nullable=True),
        sa.Column("professor_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["matricula_id"], ["matricules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modul_id"], ["moduls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["avaluacio_id"], ["avaluacions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["professor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "matricula_id", "modul_id", "avaluacio_id", name="uq_qmod_matr_modul_aval"
        ),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_qmod_matricula", "qualificacions_modul", ["matricula_id"])
    op.create_index("ix_qmod_modul", "qualificacions_modul", ["modul_id"])
    op.create_index("ix_qmod_avaluacio", "qualificacions_modul", ["avaluacio_id"])
    op.create_index("ix_qmod_aval_matr", "qualificacions_modul", ["avaluacio_id", "matricula_id"])


def downgrade() -> None:
    op.drop_index("ix_qmod_aval_matr", table_name="qualificacions_modul")
    op.drop_index("ix_qmod_avaluacio", table_name="qualificacions_modul")
    op.drop_index("ix_qmod_modul", table_name="qualificacions_modul")
    op.drop_index("ix_qmod_matricula", table_name="qualificacions_modul")
    op.drop_table("qualificacions_modul")

    op.drop_index("ix_qra_aval_matr", table_name="qualificacions_ra")
    op.drop_index("ix_qra_avaluacio", table_name="qualificacions_ra")
    op.drop_index("ix_qra_ra", table_name="qualificacions_ra")
    op.drop_index("ix_qra_matricula", table_name="qualificacions_ra")
    op.drop_table("qualificacions_ra")

    op.drop_index("ix_avaluacions_curs", table_name="avaluacions")
    op.drop_table("avaluacions")
