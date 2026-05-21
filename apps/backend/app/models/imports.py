"""Imports — track Excel/CSV uploads from admin (alumnes / matricules / notes)."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class TipusImport(StrEnum):
    ALUMNES = "alumnes"
    MATRICULES = "matricules"
    NOTES = "notes"


class EstatImport(StrEnum):
    PENDING = "pending"        # uploaded, parsed; awaiting confirm
    PROCESSING = "processing"  # commit in flight
    COMPLETED = "completed"    # done (may have row-level errors logged)
    FAILED = "failed"          # commit aborted


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tipus: Mapped[TipusImport] = mapped_column(
        SQLEnum(TipusImport, native_enum=False, length=20), nullable=False
    )
    fitxer_nom: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fitxer_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    log: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    estat: Mapped[EstatImport] = mapped_column(
        SQLEnum(EstatImport, native_enum=False, length=20),
        nullable=False,
        default=EstatImport.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User | None] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_imports_user_created", "user_id", "created_at"),
        Index("ix_imports_estat", "estat"),
    )
