"""Pydantic schemas for the auth endpoints."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Login by DNI or email + password.

    `identifier` is the user-facing field — the backend resolves which column to look up.
    """

    identifier: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, min_length=6, max_length=8)

    @field_validator("identifier")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class LoginResponse(BaseModel):
    """Returned on successful login. If the user must change password, only
    `password_change_token` is set; otherwise only `access_token` is set.
    """

    model_config = ConfigDict(use_enum_values=True)

    access_token: str | None = None
    password_change_token: str | None = None
    must_change_password: bool
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int  # seconds
    role: UserRole
    user_id: int


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int
    token_type: Literal["Bearer"] = "Bearer"


class MeResponse(BaseModel):
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
    has_mfa: bool
    has_oauth_linked: bool


class OAuthLinkRequest(BaseModel):
    """When a user has just authenticated via Google for the first time, they
    must prove possession of their existing account password before we link
    their OAuth subject. Prevents account takeover via stolen Google session.
    """

    current_password: str = Field(min_length=1, max_length=128)
