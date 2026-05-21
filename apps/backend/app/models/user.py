"""User ORM — admin and professor accounts.

Tutorship is a per-group relationship (grups_classe.tutor_user_id), not a role.
See plan §"Database schema → Identity".
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class UserRole(StrEnum):
    ADMIN = "admin"
    PROFESSOR = "professor"


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Login identifiers — DNI is primary, email accepted as alternative.
    dni: Mapped[str] = mapped_column(String(15), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    # Personal info
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    cognoms: Mapped[str] = mapped_column(String(150), nullable=False)
    departament: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Role & status
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole, native_enum=False, length=20), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    # Password (admin-generated, bcrypt; nullable when only OAuth-linked)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_set_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")

    # OAuth (optional secondary)
    oauth_subject: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    # MFA (optional, admin)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Last activity
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_users_dni", "dni"),
        Index("ix_users_email", "email"),
        Index("ix_users_role_active", "role", "active"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} dni={self.dni} role={self.role}>"
