"""Academic catalog: families, cicles, mòduls, RAs, cursos acadèmics."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Nivell(StrEnum):
    MIG = "mig"
    SUPERIOR = "superior"


class FamiliaProfessional(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "families_professionals"

    id: Mapped[int] = mapped_column(primary_key=True)
    codi: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nom: Mapped[str] = mapped_column(String(150), nullable=False)


class Cicle(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    codi: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    familia_id: Mapped[int | None] = mapped_column(
        ForeignKey("families_professionals.id", ondelete="SET NULL"), nullable=True
    )
    nivell: Mapped[Nivell] = mapped_column(
        SQLEnum(Nivell, native_enum=False, length=20), nullable=False
    )
    durada: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)

    # Política de junta per a aquest cicle. Es pot ajustar per cap d'estudis
    # sense tocar codi. Valors per defecte: convenció habitual a FP a Catalunya.
    max_suspesos_recupera: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=2, server_default="2"
    )
    pct_hores_no_promociona: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    familia: Mapped[FamiliaProfessional | None] = relationship(lazy="joined")
    moduls: Mapped[list[Modul]] = relationship(back_populates="cicle", lazy="select")


class Modul(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "moduls"

    id: Mapped[int] = mapped_column(primary_key=True)
    cicle_id: Mapped[int] = mapped_column(
        ForeignKey("cicles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(255), nullable=False)
    curs: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1 or 2
    hores: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=99)
    # Bloquejant: si l'alumne suspèn aquest mòdul, la junta no pot ratificar
    # "Apte" ni "Recupera" — passa automàticament a "No promociona". Pensat per
    # FCT, Projecte final i altres mòduls normatius bloquejants.
    bloquejant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

    cicle: Mapped[Cicle] = relationship(back_populates="moduls")
    ras: Mapped[list[Ra]] = relationship(back_populates="modul", lazy="selectin")

    __table_args__ = (UniqueConstraint("cicle_id", "codi", name="uq_modul_cicle_codi"),)


class Ra(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ras"

    id: Mapped[int] = mapped_column(primary_key=True)
    modul_id: Mapped[int] = mapped_column(
        ForeignKey("moduls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ordre: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    codi: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcio: Mapped[str] = mapped_column(Text, nullable=False)
    pes: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)

    modul: Mapped[Modul] = relationship(back_populates="ras")

    __table_args__ = (UniqueConstraint("modul_id", "ordre", name="uq_ra_modul_ordre"),)


class CursAcademic(Base, TimestampMixin):
    __tablename__ = "cursos_academics"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    actiu: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    data_inici: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fi: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (Index("ix_cursos_actiu", "actiu"),)
