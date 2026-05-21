"""People & organisation: alumnes, tutors legals, grups classe, matrícules, assignacions docents."""
from __future__ import annotations

from datetime import date
from enum import StrEnum

from sqlalchemy import (
    Date,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.catalog import Cicle, CursAcademic, Modul
from app.models.user import User


class TipusGrup(StrEnum):
    PRIMARI = "primari"
    SECUNDARI = "secundari"


class EstatMatricula(StrEnum):
    ACTIU = "actiu"
    FINALITZAT = "finalitzat"
    BAIXA = "baixa"


class Alumne(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "alumnes"

    id: Mapped[int] = mapped_column(primary_key=True)
    dni: Mapped[str | None] = mapped_column(String(15), nullable=True)
    ralc: Mapped[str] = mapped_column(String(25), nullable=False, unique=True)  # NIA / RALC
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    cognoms: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(30), nullable=True)
    data_naixement: Mapped[date | None] = mapped_column(Date, nullable=True)

    tutors_legals: Mapped[list[TutorLegal]] = relationship(
        back_populates="alumne", cascade="all, delete-orphan", lazy="select"
    )

    __table_args__ = (
        Index("ix_alumnes_dni", "dni"),
        Index("ix_alumnes_cognoms_nom", "cognoms", "nom"),
    )


class TutorLegal(Base, TimestampMixin):
    """Legal guardian / contact for an alumne. Lifecycle bound to its alumne."""

    __tablename__ = "tutors_legals"

    id: Mapped[int] = mapped_column(primary_key=True)
    alumne_id: Mapped[int] = mapped_column(
        ForeignKey("alumnes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nom: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    telefon: Mapped[str | None] = mapped_column(String(30), nullable=True)

    alumne: Mapped[Alumne] = relationship(back_populates="tutors_legals")


class GrupClasse(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "grups_classe"

    id: Mapped[int] = mapped_column(primary_key=True)
    codi: Mapped[str] = mapped_column(String(30), nullable=False)
    curs_acad_id: Mapped[int] = mapped_column(
        ForeignKey("cursos_academics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cicle_id: Mapped[int] = mapped_column(
        ForeignKey("cicles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    curs: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1 or 2
    tutor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    curs_acad: Mapped[CursAcademic] = relationship(lazy="joined")
    cicle: Mapped[Cicle] = relationship(lazy="joined")
    tutor: Mapped[User | None] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("codi", "curs_acad_id", name="uq_grup_codi_curs"),)


class Matricula(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "matricules"

    id: Mapped[int] = mapped_column(primary_key=True)
    alumne_id: Mapped[int] = mapped_column(
        ForeignKey("alumnes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grup_id: Mapped[int] = mapped_column(
        ForeignKey("grups_classe.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    cicle_id: Mapped[int] = mapped_column(
        ForeignKey("cicles.id", ondelete="RESTRICT"), nullable=False
    )
    curs: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    curs_acad_id: Mapped[int] = mapped_column(
        ForeignKey("cursos_academics.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    tipus: Mapped[TipusGrup] = mapped_column(
        SQLEnum(TipusGrup, native_enum=False, length=20),
        nullable=False,
        default=TipusGrup.PRIMARI,
    )
    estat: Mapped[EstatMatricula] = mapped_column(
        SQLEnum(EstatMatricula, native_enum=False, length=20),
        nullable=False,
        default=EstatMatricula.ACTIU,
    )

    alumne: Mapped[Alumne] = relationship(lazy="joined")
    grup: Mapped[GrupClasse] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "alumne_id", "curs_acad_id", "cicle_id", name="uq_matricula_alumne_curs_cicle"
        ),
        Index("ix_matricules_curs_estat", "curs_acad_id", "estat"),
    )


class AssignacioDocent(Base, TimestampMixin, SoftDeleteMixin):
    """Mapping: a docent (User) teaches a Mòdul to a Grup in a curs acadèmic."""

    __tablename__ = "assignacions_docents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grup_id: Mapped[int] = mapped_column(
        ForeignKey("grups_classe.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modul_id: Mapped[int] = mapped_column(
        ForeignKey("moduls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    curs_acad_id: Mapped[int] = mapped_column(
        ForeignKey("cursos_academics.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    user: Mapped[User] = relationship(lazy="joined")
    grup: Mapped[GrupClasse] = relationship(lazy="joined")
    modul: Mapped[Modul] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "grup_id", "modul_id", "curs_acad_id", name="uq_assignacio"
        ),
    )
