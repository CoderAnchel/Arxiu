"""Rate limiting via slowapi. Per-IP for auth, per-user for writes."""
from __future__ import annotations

from typing import Callable

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _user_or_ip(request: Request) -> str:
    """Key the limiter by the authenticated user when present, else by IP.
    Falls back to IP for /auth/login (no user yet)."""
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        # Cheap-tag the token suffix to distinguish users without decoding the JWT.
        return f"jwt:{auth[-16:]}"
    return get_remote_address(request)


limiter = Limiter(key_func=_user_or_ip)


def init_rate_limiter(app: FastAPI) -> None:
    settings = get_settings()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Expose limits for endpoint decorators in app.api.v1.auth
    app.state.LIMIT_LOGIN = f"{settings.rate_limit_login_per_minute}/minute"
    app.state.LIMIT_WRITE = f"{settings.rate_limit_write_per_minute}/minute"


def login_limit() -> Callable[..., str]:
    """Resolve the limit at request time so tests can override settings."""

    def fn() -> str:
        return f"{get_settings().rate_limit_login_per_minute}/minute"

    return fn


def write_limit() -> Callable[..., str]:
    def fn() -> str:
        return f"{get_settings().rate_limit_write_per_minute}/minute"

    return fn
