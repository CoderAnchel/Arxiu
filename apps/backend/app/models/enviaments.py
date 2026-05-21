"""Enviaments — log of every email the system sends (butlletins, comunicats, …)."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.people import Alumne


class TipusEnviament(StrEnum):
    BUTLLETI = "butlleti"
    COMUNICAT = "comunicat"
    RECORDATORI = "recordatori"
    CREDENCIALS = "credencials"


class EstatEnviament(StrEnum):
    QUEUED = "queued"
    ENVIAT = "enviat"
    OBERT = "obert"          # opened (requires beacon — best-effort, may stay 'enviat')
    REBOTAT = "rebotat"      # SMTP bounce
    ERROR = "error"          # internal error


class Enviament(Base):
    __tablename__ = "enviaments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    alumne_id: Mapped[int | None] = mapped_column(
        ForeignKey("alumnes.id", ondelete="SET NULL"), nullable=True
    )
    destinatari_email: Mapped[str] = mapped_column(String(150), nullable=False)
    tipus: Mapped[TipusEnviament] = mapped_column(
        SQLEnum(TipusEnviament, native_enum=False, length=20), nullable=False
    )
    assumpte: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    adjunt_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    estat: Mapped[EstatEnviament] = mapped_column(
        SQLEnum(EstatEnviament, native_enum=False, length=20),
        nullable=False,
        default=EstatEnviament.QUEUED,
    )
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optional pointers to the source data (for resending)
    avaluacio_id: Mapped[int | None] = mapped_column(
        ForeignKey("avaluacions.id", ondelete="SET NULL"), nullable=True
    )

    # Created by which user
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    alumne: Mapped[Alumne | None] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_enviaments_estat", "estat"),
        Index("ix_enviaments_alumne", "alumne_id"),
        Index("ix_enviaments_aval", "avaluacio_id"),
        Index("ix_enviaments_queued", "queued_at"),
    )
