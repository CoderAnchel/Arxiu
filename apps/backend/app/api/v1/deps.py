"""FastAPI dependencies — DB session, current user, role guards."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions, security
from app.core.exceptions import (
    AccountInactive,
    InvalidToken,
    PasswordChangeRequired,
    TokenScopeInsufficient,
)
from app.db.session import get_db as _get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async for s in _get_db():
        yield s


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _user_from_token(
    session: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
    *,
    expected_type: str = "access",
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = security.decode_token(credentials.credentials, expected_type=expected_type)  # type: ignore[arg-type]
    except TokenScopeInsufficient as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.code) from exc
    except InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.code) from exc

    user = await session.get(User, int(claims.sub))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_not_found")
    return user


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    user = await _user_from_token(db, creds, expected_type="access")
    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, AccountInactive.code)
    if user.must_change_password:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, PasswordChangeRequired.code)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_password_change_scope(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Accept either a normal access token or a password-change-scoped token.
    Used by the change-password endpoint so users with must_change_password=True
    can call it after login."""
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = security.decode_token(creds.credentials)
    except InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.code) from exc

    if claims.typ not in ("access", "password_change"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token_scope_insufficient")

    user = await db.get(User, int(claims.sub))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user_not_found")
    return user


def require_admin(user: CurrentUser) -> User:
    if not permissions.is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_request_metadata(request: Request) -> dict[str, str | None]:
    """Extract IP + UA for audit logs. Trusts X-Forwarded-For only when set by our reverse proxy."""
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else None)
    return {"ip": ip, "user_agent": request.headers.get("user-agent")}
