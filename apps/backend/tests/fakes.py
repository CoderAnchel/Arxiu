"""In-memory fakes used by tests."""
from __future__ import annotations

import asyncio
import time


class FakeRedis:
    """Minimal subset of redis.asyncio.Redis used by `app/db/redis.py`."""

    def __init__(self) -> None:
        self._kv: dict[str, tuple[str, float | None]] = {}
        self._sets: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    def _expired(self, key: str) -> bool:
        v = self._kv.get(key)
        if v is None:
            return True
        _, exp = v
        return exp is not None and exp < time.time()

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        async with self._lock:
            exp = time.time() + ex if ex else None
            self._kv[key] = (value, exp)
        return True

    async def get(self, key: str) -> str | None:
        async with self._lock:
            if self._expired(key):
                self._kv.pop(key, None)
                return None
            v = self._kv.get(key)
            return v[0] if v else None

    async def getdel(self, key: str) -> str | None:
        async with self._lock:
            if self._expired(key):
                self._kv.pop(key, None)
                return None
            v = self._kv.pop(key, None)
            return v[0] if v else None

    async def delete(self, *keys: str) -> int:
        async with self._lock:
            n = 0
            for k in keys:
                if k in self._kv:
                    del self._kv[k]
                    n += 1
                if k in self._sets:
                    del self._sets[k]
                    n += 1
            return n

    async def exists(self, key: str) -> int:
        async with self._lock:
            if key in self._kv and not self._expired(key):
                return 1
            return 1 if key in self._sets else 0

    async def expire(self, key: str, ex: int) -> bool:
        async with self._lock:
            v = self._kv.get(key)
            if v is not None:
                self._kv[key] = (v[0], time.time() + ex)
                return True
            return False

    async def sadd(self, key: str, *members: str) -> int:
        async with self._lock:
            s = self._sets.setdefault(key, set())
            before = len(s)
            s.update(members)
            return len(s) - before

    async def srem(self, key: str, *members: str) -> int:
        async with self._lock:
            s = self._sets.get(key, set())
            before = len(s)
            for m in members:
                s.discard(m)
            return before - len(s)

    async def smembers(self, key: str) -> set[str]:
        async with self._lock:
            return set(self._sets.get(key, set()))

    async def aclose(self) -> None:
        pass
