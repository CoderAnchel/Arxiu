"""Auth service — login, refresh, password change. No HTTP concerns here."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import (
    AccountInactive,
    InvalidCredentials,
    InvalidToken,
    PasswordChangeRequired,
)
from app.db import redis as redis_helpers
from app.models.user import User
from app.services import audit


async def lookup_user(session: AsyncSession, identifier: str) -> User | None:
    """Find user by DNI (case-insensitive) or email (case-insensitive)."""
    ident = identifier.strip()
    stmt = (
        select(User)
        .where(
            or_(
                User.dni == ident.upper(),
                User.email == ident.lower(),
            ),
            User.deleted_at.is_(None),
        )
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def authenticate(
    session: AsyncSession,
    *,
    identifier: str,
    password: str,
    totp_code: str | None,
    ip: str | None,
    user_agent: str | None,
) -> User:
    """Returns the authenticated user. Raises on any failure (invalid creds, inactive,
    MFA failure). Caller decides whether to issue a normal access token or a
    password-change-scoped token based on user.must_change_password."""
    user = await lookup_user(session, identifier)
    if user is None or user.password_hash is None:
        await audit.record(
            session,
            action="login_failed",
            entity="auth",
            user_id=None,
            after={"reason": "user_not_found", "identifier": identifier[:50]},
            ip=ip,
            user_agent=user_agent,
        )
        raise InvalidCredentials()

    if not security.verify_password(password, user.password_hash):
        await audit.record(
            session,
            action="login_failed",
            entity="auth",
            user_id=user.id,
            after={"reason": "bad_password"},
            ip=ip,
            user_agent=user_agent,
        )
        raise InvalidCredentials()

    if not user.active:
        raise AccountInactive()

    # MFA check (only when secret is set on the user)
    if user.mfa_secret:
        if not totp_code or not security.verify_totp(user.mfa_secret, totp_code):
            await audit.record(
                session,
                action="login_failed",
                entity="auth",
                user_id=user.id,
                after={"reason": "mfa_failed"},
                ip=ip,
                user_agent=user_agent,
            )
            raise InvalidCredentials()

    user.last_login_at = datetime.now(timezone.utc)

    await audit.record(
        session,
        action="login_success",
        entity="auth",
        user_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )

    return user


async def issue_login_tokens(user: User) -> tuple[str | None, str | None, str | None, int]:
    """Returns (access_token, password_change_token, refresh_token, expires_in).

    If `must_change_password` is True, only `password_change_token` is set and
    no refresh token is issued — the user must change password first.
    """
    settings = get_settings()
    if user.must_change_password:
        token, claims = security.issue_password_change_token(user_id=user.id, role=user.role.value)
        return None, token, None, claims.exp - int(datetime.now(timezone.utc).timestamp())

    access, _ = security.issue_access_token(user_id=user.id, role=user.role.value)
    refresh, refresh_claims = security.issue_refresh_token(user_id=user.id, role=user.role.value)
    assert refresh_claims.fam is not None
    await redis_helpers.register_refresh(
        jti=refresh_claims.jti,
        user_id=user.id,
        family_id=refresh_claims.fam,
        ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )
    return access, None, refresh, settings.jwt_access_ttl_seconds


async def refresh_access_token(refresh_token: str) -> tuple[str, str, int]:
    """Rotate a refresh token. Returns (new_access, new_refresh, access_expires_in).

    Reuse detection: if the presented jti has already been consumed, the entire
    family is revoked and InvalidToken is raised.
    """
    settings = get_settings()
    claims = security.decode_token(refresh_token, expected_type="refresh")
    if not claims.fam:
        raise InvalidToken("refresh token missing family")

    meta = await redis_helpers.consume_refresh(claims.jti)
    if meta is None:
        # Reuse or revoked — revoke the family as a precaution
        await redis_helpers.revoke_family(claims.fam, ttl_seconds=settings.jwt_refresh_ttl_seconds)
        raise InvalidToken("refresh token reuse or revoked")

    user_id = int(claims.sub)
    role = claims.role

    new_access, _ = security.issue_access_token(user_id=user_id, role=role)
    new_refresh, new_refresh_claims = security.issue_refresh_token(
        user_id=user_id, role=role, family_id=claims.fam
    )
    assert new_refresh_claims.fam is not None
    await redis_helpers.register_refresh(
        jti=new_refresh_claims.jti,
        user_id=user_id,
        family_id=new_refresh_claims.fam,
        ttl_seconds=settings.jwt_refresh_ttl_seconds,
    )
    return new_access, new_refresh, settings.jwt_access_ttl_seconds


async def revoke_refresh(refresh_token: str) -> None:
    """Best-effort revocation on logout. Decoding errors are swallowed."""
    settings = get_settings()
    try:
        claims = security.decode_token(refresh_token, expected_type="refresh")
    except Exception:
        return
    if claims.fam:
        await redis_helpers.revoke_family(claims.fam, ttl_seconds=settings.jwt_refresh_ttl_seconds)


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str | None,
    new_password: str,
    bypass_current_check: bool = False,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Change a user's password. If `bypass_current_check` is True, skips the
    current-password verification — used right after admin-generated password
    where the user has just authenticated with the temp password.
    """
    if not bypass_current_check:
        if user.password_hash is None or current_password is None:
            raise InvalidCredentials()
        if not security.verify_password(current_password, user.password_hash):
            await audit.record(
                session,
                action="password_change_failed",
                entity="user",
                entity_id=user.id,
                user_id=user.id,
                after={"reason": "bad_current_password"},
                ip=ip,
                user_agent=user_agent,
            )
            raise InvalidCredentials()

    user.password_hash = security.hash_password(new_password)
    user.password_set_at = datetime.now(timezone.utc)
    user.password_set_by_user_id = user.id
    user.must_change_password = False

    await audit.record(
        session,
        action="password_changed",
        entity="user",
        entity_id=user.id,
        user_id=user.id,
        ip=ip,
        user_agent=user_agent,
    )


async def require_active(user: User) -> None:
    if not user.active:
        raise AccountInactive()
    if user.must_change_password:
        raise PasswordChangeRequired()
