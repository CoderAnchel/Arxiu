"""catalog + people: families, cicles, moduls, ras, cursos, alumnes, tutors,
grups, matricules, assignacions_docents.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-07
"""
from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- Catalog -----------------------------------------------------------
    op.create_table(
        "families_professionals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codi", sa.String(20), nullable=False),
        sa.Column("nom", sa.String(150), nullable=False),
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
        sa.UniqueConstraint("codi", name="uq_families_codi"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )

    op.create_table(
        "cicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codi", sa.String(20), nullable=False),
        sa.Column("nom", sa.String(255), nullable=False),
        sa.Column("familia_id", sa.Integer(), nullable=True),
        sa.Column(
            "nivell",
            sa.Enum("mig", "superior", name="nivell", native_enum=False, length=20),
            nullable=False,
        ),
        sa.Column("durada", sa.SmallInteger(), nullable=False, server_default="2"),
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
        sa.ForeignKeyConstraint(["familia_id"], ["families_professionals.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("codi", name="uq_cicles_codi"),
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "moduls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cicle_id", sa.Integer(), nullable=False),
        sa.Column("codi", sa.String(20), nullable=False),
        sa.Column("nom", sa.String(255), nullable=False),
        sa.Column("curs", sa.SmallInteger(), nullable=False),
        sa.Column("hores", sa.SmallInteger(), nullable=False, server_default="99"),
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
        sa.ForeignKeyConstraint(["cicle_id"], ["cicles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("cicle_id", "codi", name="uq_modul_cicle_codi"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_moduls_cicle_id", "moduls", ["cicle_id"])

    op.create_table(
        "ras",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("modul_id", sa.Integer(), nullable=False),
        sa.Column("ordre", sa.SmallInteger(), nullable=False),
        sa.Column("codi", sa.String(20), nullable=False),
        sa.Column("descripcio", sa.Text(), nullable=False),
        sa.Column("pes", sa.Numeric(5, 2), nullable=False, server_default="0"),
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
        sa.ForeignKeyConstraint(["modul_id"], ["moduls.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("modul_id", "ordre", name="uq_ra_modul_ordre"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_ras_modul_id", "ras", ["modul_id"])

    op.create_table(
        "cursos_academics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("nom", sa.String(20), nullable=False),
        sa.Column("actiu", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("data_inici", sa.Date(), nullable=True),
        sa.Column("data_fi", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("nom", name="uq_cursos_nom"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_cursos_actiu", "cursos_academics", ["actiu"])

    # --- People ------------------------------------------------------------
    op.create_table(
        "alumnes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dni", sa.String(15), nullable=True),
        sa.Column("ralc", sa.String(25), nullable=False),
        sa.Column("nom", sa.String(100), nullable=False),
        sa.Column("cognoms", sa.String(150), nullable=False),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("telefon", sa.String(30), nullable=True),
        sa.Column("data_naixement", sa.Date(), nullable=True),
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
        sa.UniqueConstraint("ralc", name="uq_alumnes_ralc"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_alumnes_dni", "alumnes", ["dni"])
    op.create_index("ix_alumnes_cognoms_nom", "alumnes", ["cognoms", "nom"])

    op.create_table(
        "tutors_legals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alumne_id", sa.Integer(), nullable=False),
        sa.Column("nom", sa.String(150), nullable=False),
        sa.Column("email", sa.String(150), nullable=True),
        sa.Column("telefon", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["alumne_id"], ["alumnes.id"], ondelete="CASCADE"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_tutors_alumne_id", "tutors_legals", ["alumne_id"])

    op.create_table(
        "grups_classe",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codi", sa.String(30), nullable=False),
        sa.Column("curs_acad_id", sa.Integer(), nullable=False),
        sa.Column("cicle_id", sa.Integer(), nullable=False),
        sa.Column("curs", sa.SmallInteger(), nullable=False),
        sa.Column("tutor_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["cicle_id"], ["cicles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tutor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("codi", "curs_acad_id", name="uq_grup_codi_curs"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_grups_curs_acad", "grups_classe", ["curs_acad_id"])
    op.create_index("ix_grups_cicle", "grups_classe", ["cicle_id"])

    op.create_table(
        "matricules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("alumne_id", sa.Integer(), nullable=False),
        sa.Column("grup_id", sa.Integer(), nullable=False),
        sa.Column("cicle_id", sa.Integer(), nullable=False),
        sa.Column("curs", sa.SmallInteger(), nullable=False),
        sa.Column("curs_acad_id", sa.Integer(), nullable=False),
        sa.Column(
            "tipus",
            sa.Enum("primari", "secundari", name="tipusgrup", native_enum=False, length=20),
            nullable=False,
            server_default="primari",
        ),
        sa.Column(
            "estat",
            sa.Enum("actiu", "finalitzat", "baixa", name="estatmatricula", native_enum=False, length=20),
            nullable=False,
            server_default="actiu",
        ),
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
        sa.ForeignKeyConstraint(["alumne_id"], ["alumnes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grup_id"], ["grups_classe.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["cicle_id"], ["cicles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["curs_acad_id"], ["cursos_academics.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "alumne_id", "curs_acad_id", "cicle_id", name="uq_matricula_alumne_curs_cicle"
        ),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_matricules_alumne", "matricules", ["alumne_id"])
    op.create_index("ix_matricules_grup", "matricules", ["grup_id"])
    op.create_index("ix_matricules_curs_estat", "matricules", ["curs_acad_id", "estat"])

    op.create_table(
        "assignacions_docents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("grup_id", sa.Integer(), nullable=False),
        sa.Column("modul_id", sa.Integer(), nullable=False),
        sa.Column("curs_acad_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["grup_id"], ["grups_classe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["modul_id"], ["moduls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["curs_acad_id"], ["cursos_academics.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "grup_id", "modul_id", "curs_acad_id", name="uq_assignacio"),
        mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    op.drop_table("assignacions_docents")
    op.drop_index("ix_matricules_curs_estat", table_name="matricules")
    op.drop_index("ix_matricules_grup", table_name="matricules")
    op.drop_index("ix_matricules_alumne", table_name="matricules")
    op.drop_table("matricules")
    op.drop_index("ix_grups_cicle", table_name="grups_classe")
    op.drop_index("ix_grups_curs_acad", table_name="grups_classe")
    op.drop_table("grups_classe")
    op.drop_index("ix_tutors_alumne_id", table_name="tutors_legals")
    op.drop_table("tutors_legals")
    op.drop_index("ix_alumnes_cognoms_nom", table_name="alumnes")
    op.drop_index("ix_alumnes_dni", table_name="alumnes")
    op.drop_table("alumnes")
    op.drop_index("ix_cursos_actiu", table_name="cursos_academics")
    op.drop_table("cursos_academics")
    op.drop_index("ix_ras_modul_id", table_name="ras")
    op.drop_table("ras")
    op.drop_index("ix_moduls_cicle_id", table_name="moduls")
    op.drop_table("moduls")
    op.drop_table("cicles")
    op.drop_table("families_professionals")
