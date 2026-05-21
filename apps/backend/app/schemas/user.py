"""Pydantic schemas for admin user management."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole


def _validate_dni(v: str) -> str:
    """DNI/NIE: 8 digits + letter (DNI) or X/Y/Z + 7 digits + letter (NIE)."""
    v = v.strip().upper()
    if len(v) < 8 or len(v) > 15:
        raise ValueError("DNI/NIE must be between 8 and 15 characters")
    return v


class UserCreate(BaseModel):
    dni: str = Field(min_length=8, max_length=15)
    email: EmailStr
    nom: str = Field(min_length=1, max_length=100)
    cognoms: str = Field(min_length=1, max_length=150)
    role: UserRole
    departament: str | None = Field(default=None, max_length=100)

    _normalize_dni = field_validator("dni")(lambda v: _validate_dni(v))


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    cognoms: str | None = Field(default=None, min_length=1, max_length=150)
    departament: str | None = Field(default=None, max_length=100)
    role: UserRole | None = None
    active: bool | None = None


class UserResponse(BaseModel):
    """Public user representation. Never includes password_hash or mfa_secret."""

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    dni: str
    email: str
    nom: str
    cognoms: str
    departament: str | None
    role: UserRole
    active: bool
    must_change_password: bool
    has_oauth_linked: bool
    has_mfa: bool
    last_login_at: datetime | None
    created_at: datetime


class UserCreateResponse(UserResponse):
    """One-time response after admin creates a user — includes the generated
    plaintext password. The plaintext is **never** stored or returned again.
    """

    generated_password: str = Field(description="Reveal-once plaintext password — admin distributes manually or via email-password endpoint within 5 minutes")


class PasswordRegenerateResponse(BaseModel):
    user_id: int
    generated_password: str = Field(description="Reveal-once plaintext password")


class BulkPasswordRow(BaseModel):
    user_id: int
    dni: str
    email: str
    nom: str
    cognoms: str
    generated_password: str


class BulkPasswordRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=200)


class BulkPasswordResponse(BaseModel):
    rows: list[BulkPasswordRow]
