"""Async-friendly factories for tests."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.models.user import User, UserRole


async def make_user(
    session: AsyncSession,
    *,
    dni: str = "12345678Z",
    email: str = "user@inslaferreria.cat",
    nom: str = "Sergi",
    cognoms: str = "Veciana",
    role: UserRole = UserRole.PROFESSOR,
    password: str | None = "Initial-Password-1!",
    must_change_password: bool = False,
    active: bool = True,
    departament: str | None = "Informàtica",
    mfa_secret: str | None = None,
) -> User:
    user = User(
        dni=dni.upper(),
        email=email.lower(),
        nom=nom,
        cognoms=cognoms,
        role=role,
        active=active,
        password_hash=security.hash_password(password) if password else None,
        password_set_at=datetime.now(timezone.utc) if password else None,
        must_change_password=must_change_password,
        departament=departament,
        mfa_secret=mfa_secret,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def make_admin(session: AsyncSession, **kw) -> User:  # type: ignore[no-untyped-def]
    kw.setdefault("dni", "11111111A")
    kw.setdefault("email", "admin@inslaferreria.cat")
    kw.setdefault("nom", "Admin")
    kw.setdefault("cognoms", "Centre")
    kw.setdefault("role", UserRole.ADMIN)
    return await make_user(session, **kw)
