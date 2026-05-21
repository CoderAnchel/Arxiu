"""Production-only minimal seed: creates the first admin and exits.
Use this on Windows Server — never run the full demo `seed.py` in prod.

Run:
    docker compose ... exec backend python -m app.scripts.seed_admin
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core import security
from app.db.session import get_engine
from app.models.user import User, UserRole

ADMIN_DNI = "00000000T"
ADMIN_EMAIL = "admin@inslaferreria.cat"
ADMIN_NOM = "Administrador"
ADMIN_COGNOMS = "Centre"


async def main() -> None:
    engine = get_engine()
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with SessionFactory() as session:
        existing = (
            await session.execute(select(User).where(User.dni == ADMIN_DNI))
        ).scalar_one_or_none()

        if existing is not None and existing.password_hash is not None:
            print(f"Admin {ADMIN_DNI} ja existeix amb contrasenya configurada. No s'ha fet res.")
            print("Per regenerar la contrasenya, esborra l'usuari o usa l'endpoint d'admin.")
            return

        plaintext = security.generate_password()
        if existing is None:
            admin = User(
                dni=ADMIN_DNI,
                email=ADMIN_EMAIL,
                nom=ADMIN_NOM,
                cognoms=ADMIN_COGNOMS,
                role=UserRole.ADMIN,
                active=True,
                password_hash=security.hash_password(plaintext),
                password_set_at=datetime.now(timezone.utc),
                must_change_password=True,
            )
            session.add(admin)
        else:
            existing.password_hash = security.hash_password(plaintext)
            existing.password_set_at = datetime.now(timezone.utc)
            existing.must_change_password = True

        await session.commit()

    print()
    print("=" * 60)
    print("  ARXIU — credencials d'administrador (primer accés)")
    print("=" * 60)
    print(f"  DNI:         {ADMIN_DNI}")
    print(f"  Email:       {ADMIN_EMAIL}")
    print(f"  Contrasenya: {plaintext}")
    print()
    print("  → Accedeix al portal i canvia-la immediatament.")
    print("  → Aquesta contrasenya NO es tornarà a mostrar.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
