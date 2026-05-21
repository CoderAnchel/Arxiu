"""Domain exceptions — translated to HTTP responses by the FastAPI exception handler."""
from __future__ import annotations


class ArxiuError(Exception):
    """Base for all domain errors."""

    code: str = "internal_error"
    http_status: int = 500

    def __init__(self, message: str | None = None, *, detail: dict | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.detail = detail or {}


# --- Authentication / authorisation ----------------------------------------

class AuthError(ArxiuError):
    code = "auth_error"
    http_status = 401


class InvalidCredentials(AuthError):
    code = "invalid_credentials"


class AccountInactive(AuthError):
    code = "account_inactive"
    http_status = 403


class PasswordChangeRequired(AuthError):
    code = "password_change_required"
    http_status = 401


class InvalidToken(AuthError):
    code = "invalid_token"


class TokenExpired(AuthError):
    code = "token_expired"


class TokenScopeInsufficient(AuthError):
    code = "token_scope_insufficient"
    http_status = 403


class PermissionDenied(ArxiuError):
    code = "permission_denied"
    http_status = 403


# --- Resources --------------------------------------------------------------

class NotFound(ArxiuError):
    code = "not_found"
    http_status = 404


class Conflict(ArxiuError):
    code = "conflict"
    http_status = 409


class ValidationError(ArxiuError):
    code = "validation_error"
    http_status = 422


# --- Rate limiting ----------------------------------------------------------

class RateLimited(ArxiuError):
    code = "rate_limited"
    http_status = 429
