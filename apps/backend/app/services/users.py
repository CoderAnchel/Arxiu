"""User CRUD + admin password management."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import get_settings
from app.core.exceptions import Conflict, NotFound
from app.db import redis as redis_helpers
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import audit


async def create_user(
    session: AsyncSession,
    *,
    payload: UserCreate,
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    """Create a user with an admin-generated password. Returns (user, plaintext).

    Plaintext is also stored in Redis under a TTL so the admin can trigger
    an email-password action shortly after.
    """
    settings = get_settings()
    plaintext = security.generate_password()

    user = User(
        dni=payload.dni.upper(),
        email=str(payload.email).lower(),
        nom=payload.nom,
        cognoms=payload.cognoms,
        departament=payload.departament,
        role=payload.role,
        active=True,
        password_hash=security.hash_password(plaintext),
        password_set_at=datetime.now(timezone.utc),
        password_set_by_user_id=actor_id,
        must_change_password=True,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("user with this DNI or email already exists") from exc

    await redis_helpers.store_password_reveal(
        user.id, plaintext, ttl_seconds=settings.admin_password_reveal_ttl_seconds
    )

    await audit.record(
        session,
        action="user_created",
        entity="user",
        entity_id=user.id,
        user_id=actor_id,
        after={"dni": user.dni, "email": user.email, "role": user.role.value},
        ip=ip,
        user_agent=user_agent,
    )
    # Ensure server-populated fields (created_at, updated_at, etc.) are loaded
    # before returning the ORM object. This avoids triggering a lazy-load that
    # would perform IO from a synchronous context later (causing
    # "greenlet_spawn has not been called" errors with async drivers).
    await session.refresh(user)
    return user, plaintext


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFound("user not found")
    return user


async def list_users(session: AsyncSession, *, include_deleted: bool = False) -> list[User]:
    stmt = select(User).order_by(User.cognoms, User.nom)
    if not include_deleted:
        stmt = stmt.where(User.deleted_at.is_(None))
    return list((await session.execute(stmt)).scalars().all())


async def update_user(
    session: AsyncSession,
    *,
    user_id: int,
    payload: UserUpdate,
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> User:
    user = await get_user(session, user_id)
    before = {
        "email": user.email,
        "nom": user.nom,
        "cognoms": user.cognoms,
        "departament": user.departament,
        "role": user.role.value,
        "active": user.active,
    }
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"] is not None:
        data["email"] = str(data["email"]).lower()
    for k, v in data.items():
        setattr(user, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update violates a uniqueness constraint") from exc

    await audit.record(
        session,
        action="user_updated",
        entity="user",
        entity_id=user.id,
        user_id=actor_id,
        before=before,
        after={k: getattr(user, k) for k in before},
        ip=ip,
        user_agent=user_agent,
    )
    return user


async def soft_delete_user(
    session: AsyncSession,
    *,
    user_id: int,
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> None:
    user = await get_user(session, user_id)
    if user.id == actor_id:
        raise Conflict("cannot delete your own account")
    user.deleted_at = datetime.now(timezone.utc)
    user.deleted_by_user_id = actor_id
    user.active = False
    await audit.record(
        session,
        action="user_soft_deleted",
        entity="user",
        entity_id=user.id,
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
    )


async def regenerate_password(
    session: AsyncSession,
    *,
    user_id: int,
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[User, str]:
    settings = get_settings()
    user = await get_user(session, user_id)
    plaintext = security.generate_password()
    user.password_hash = security.hash_password(plaintext)
    user.password_set_at = datetime.now(timezone.utc)
    user.password_set_by_user_id = actor_id
    user.must_change_password = True

    await redis_helpers.store_password_reveal(
        user.id, plaintext, ttl_seconds=settings.admin_password_reveal_ttl_seconds
    )

    await audit.record(
        session,
        action="password_regenerated",
        entity="user",
        entity_id=user.id,
        user_id=actor_id,
        ip=ip,
        user_agent=user_agent,
    )
    return user, plaintext


async def bulk_regenerate_passwords(
    session: AsyncSession,
    *,
    user_ids: list[int],
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> list[tuple[User, str]]:
    out: list[tuple[User, str]] = []
    for uid in user_ids:
        user, plaintext = await regenerate_password(
            session, user_id=uid, actor_id=actor_id, ip=ip, user_agent=user_agent
        )
        out.append((user, plaintext))
    return out


async def fetch_password_reveal(user_id: int) -> str | None:
    """Read once from Redis. Returns the plaintext password if still in window."""
    return await redis_helpers.consume_password_reveal(user_id)
