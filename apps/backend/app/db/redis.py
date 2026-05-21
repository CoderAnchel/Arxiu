"""Redis client + helpers for refresh tokens and password reveal tokens."""
from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client


# --- Refresh token registry -------------------------------------------------
#
# Each refresh token is recorded under `refresh:{jti}` → JSON metadata.
# A separate `refresh-fam:{family_id}` set tracks all jti's belonging to a
# family so we can revoke the entire family on reuse detection.

_REFRESH_KEY = "refresh:{jti}"
_FAMILY_KEY = "refresh-fam:{family_id}"
_REVOKED_FAMILY = "refresh-fam-revoked:{family_id}"


async def register_refresh(*, jti: str, user_id: int, family_id: str, ttl_seconds: int) -> None:
    r = get_redis()
    payload = json.dumps({"user_id": user_id, "family_id": family_id})
    await r.set(_REFRESH_KEY.format(jti=jti), payload, ex=ttl_seconds)
    await r.sadd(_FAMILY_KEY.format(family_id=family_id), jti)
    await r.expire(_FAMILY_KEY.format(family_id=family_id), ttl_seconds)


async def consume_refresh(jti: str) -> dict[str, Any] | None:
    """Atomic 'use once': returns metadata if valid, else None.
    Reuse detection: if family revoked or jti not present, returns None.
    """
    r = get_redis()
    raw = await r.get(_REFRESH_KEY.format(jti=jti))
    if raw is None:
        return None
    meta = json.loads(raw)
    family_id = meta["family_id"]
    if await r.exists(_REVOKED_FAMILY.format(family_id=family_id)):
        return None
    # Mark this jti as used by deleting it. The new jti gets registered under same family.
    await r.delete(_REFRESH_KEY.format(jti=jti))
    await r.srem(_FAMILY_KEY.format(family_id=family_id), jti)
    return meta


async def revoke_family(family_id: str, *, ttl_seconds: int = 7 * 24 * 3600) -> None:
    r = get_redis()
    # Delete all jti's in the family
    members = await r.smembers(_FAMILY_KEY.format(family_id=family_id))
    if members:
        await r.delete(*[_REFRESH_KEY.format(jti=jti) for jti in members])
    await r.delete(_FAMILY_KEY.format(family_id=family_id))
    # Tombstone — any future use of a token claiming this family is rejected
    await r.set(_REVOKED_FAMILY.format(family_id=family_id), "1", ex=ttl_seconds)


# --- Password reveal tokens -------------------------------------------------
#
# After admin generates a password we store the plaintext under a 5-min TTL key
# so the admin can trigger an "email password" action without us re-storing
# plaintext beyond that window.

_REVEAL_KEY = "pw-reveal:{user_id}"


async def store_password_reveal(user_id: int, plaintext: str, *, ttl_seconds: int) -> None:
    r = get_redis()
    await r.set(_REVEAL_KEY.format(user_id=user_id), plaintext, ex=ttl_seconds)


async def consume_password_reveal(user_id: int) -> str | None:
    r = get_redis()
    raw = await r.getdel(_REVEAL_KEY.format(user_id=user_id))
    return raw if isinstance(raw, str) else None
