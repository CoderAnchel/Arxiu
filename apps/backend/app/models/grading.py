"""Avaluacions + qualificacions (per RA and per mòdul)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.catalog import CursAcademic, Modul, Ra
from app.models.people import Matricula
from app.models.user import User


class EstatAvaluacio(StrEnum):
    OBERTA = "oberta"      # initial config; admin assigns docents
    DOCENT = "docent"      # professors enter notes for their assigned moduls
    JUNTA = "junta"        # tutor reviews and may edit any nota in their grup
    TANCADA = "tancada"    # locked; PDFs generated and emails sent


class Avaluacio(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "avaluacions"

    id: Mapped[int] = mapped_column(primary_key=True)
    curs_acad_id: Mapped[int] = mapped_column(
        ForeignKey("cursos_academics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    ordre: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    estat: Mapped[EstatAvaluacio] = mapped_column(
        SQLEnum(EstatAvaluacio, native_enum=False, length=20),
        nullable=False,
        default=EstatAvaluacio.OBERTA,
    )
    data_inici: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_tancament: Mapped[date | None] = mapped_column(Date, nullable=True)

    curs_acad: Mapped[CursAcademic] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("curs_acad_id", "ordre", name="uq_avaluacio_curs_ordre"),
    )


class QualificacioRa(Base):
    """One nota per (matrícula, RA, avaluació)."""

    __tablename__ = "qualificacions_ra"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(
        ForeignKey("matricules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ra_id: Mapped[int] = mapped_column(
        ForeignKey("ras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avaluacio_id: Mapped[int] = mapped_column(
        ForeignKey("avaluacions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    nota: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    comentari: Mapped[str | None] = mapped_column(Text, nullable=True)

    professor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    updated_at: Mapped[date | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    matricula: Mapped[Matricula] = relationship(lazy="joined")
    ra: Mapped[Ra] = relationship(lazy="joined")
    professor: Mapped[User | None] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint("matricula_id", "ra_id", "avaluacio_id", name="uq_qra_matr_ra_aval"),
        Index("ix_qra_aval_matr", "avaluacio_id", "matricula_id"),
    )


class QualificacioModul(Base):
    """One final mòdul nota per (matrícula, mòdul, avaluació)."""

    __tablename__ = "qualificacions_modul"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula_id: Mapped[int] = mapped_column(
        ForeignKey("matricules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modul_id: Mapped[int] = mapped_column(
        ForeignKey("moduls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avaluacio_id: Mapped[int] = mapped_column(
        ForeignKey("avaluacions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    nota: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    comentari: Mapped[str | None] = mapped_column(Text, nullable=True)

    professor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    updated_at: Mapped[date | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    matricula: Mapped[Matricula] = relationship(lazy="joined")
    modul: Mapped[Modul] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "matricula_id", "modul_id", "avaluacio_id", name="uq_qmod_matr_modul_aval"
        ),
        Index("ix_qmod_aval_matr", "avaluacio_id", "matricula_id"),
    )
