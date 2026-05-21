"""junta policies: bloquejant per mòdul + llindar i % hores per cicle

Adds three columns that drive the automatic decision proposal on the acta
de junta d'avaluació:

  - moduls.bloquejant (BOOL) — un suspès aquí força "No promociona"
  - cicles.max_suspesos_recupera (SMALLINT, default 2) — fins quants
    suspesos comporten "Recupera" en lloc de "No promociona"
  - cicles.pct_hores_no_promociona (DECIMAL(5,2), NULL) — regla opcional:
    si el % d'hores suspeses supera aquest valor, "No promociona"
    independentment del recompte.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-20
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "moduls",
        sa.Column(
            "bloquejant",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "cicles",
        sa.Column(
            "max_suspesos_recupera",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("2"),
        ),
    )
    op.add_column(
        "cicles",
        sa.Column(
            "pct_hores_no_promociona",
            sa.Numeric(5, 2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("cicles", "pct_hores_no_promociona")
    op.drop_column("cicles", "max_suspesos_recupera")
    op.drop_column("moduls", "bloquejant")
