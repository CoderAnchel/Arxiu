"""Shared pytest fixtures.

Strategy: every test runs against an isolated SQLite database (aiosqlite). For
schema parity with MySQL, the migration is *not* run — instead Base.metadata
creates tables. Production-only constructs (server-defaults, TIMESTAMP timezone
behaviour) are validated separately in CI against MySQL via the integration
runner.
"""
from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# --- JWT keypair fixture-side ----------------------------------------------
# Generate a transient keypair for the test session before importing app code.

@pytest.fixture(scope="session", autouse=True)
def _jwt_keys(tmp_path_factory: pytest.TempPathFactory) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    keys_dir = tmp_path_factory.mktemp("jwt-keys")
    priv_path = keys_dir / "jwt_private.pem"
    pub_path = keys_dir / "jwt_public.pem"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    os.environ["JWT_PRIVATE_KEY_PATH"] = str(priv_path)
    os.environ["JWT_PUBLIC_KEY_PATH"] = str(pub_path)

    # SQLite for the session
    db_file = keys_dir / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"
    os.environ["REDIS_URL"] = "redis://localhost:6379/15"
    os.environ["APP_ENV"] = "development"
    os.environ.setdefault("MYSQL_DATABASE", "arxiu")
    os.environ.setdefault("MYSQL_USER", "arxiu")
    os.environ.setdefault("MYSQL_PASSWORD", "test")

    # Reset cached settings + engines after env mutation
    from app.core.config import get_settings as _gs

    _gs.cache_clear()  # type: ignore[attr-defined]


# --- DB engine + session ----------------------------------------------------

@pytest.fixture
async def engine():
    from app.db.base import Base

    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    async with engine.begin() as conn:
        # Pull in all models so metadata is populated
        import app.models  # noqa: F401
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()


# --- HTTP client ------------------------------------------------------------

def _reset_prometheus_registry() -> None:
    """Unregister every collector from the default Prometheus registry.

    `create_app()` calls `init_prometheus(app)` which registers Counter/Histogram
    instances at the module level. The default registry is a singleton, so when
    tests call `create_app()` more than once in the same process (which happens
    in CI because tests share a process) it raises `Duplicated timeseries`.
    Clearing the registry before each test makes the app factory idempotent
    from the tests' point of view, without changing any production code.
    """
    from prometheus_client import REGISTRY

    for collector in list(REGISTRY._collector_to_names.keys()):  # type: ignore[attr-defined]
        try:
            REGISTRY.unregister(collector)
        except Exception:
            # Default Python collectors raise when unregistered; harmless.
            pass


@pytest.fixture
async def client(engine, monkeypatch) -> AsyncIterator[AsyncClient]:
    """An ASGI client with the engine wired into get_db() and a fake Redis."""
    from app.api.v1.deps import get_db as deps_get_db
    from app.db import redis as redis_module
    from app.db.session import get_db as session_get_db
    from app.main import create_app
    from tests.fakes import FakeRedis

    fake_redis = FakeRedis()
    monkeypatch.setattr(redis_module, "get_redis", lambda: fake_redis)

    _reset_prometheus_registry()
    app = create_app()

    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[deps_get_db] = override_get_db
    app.dependency_overrides[session_get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
