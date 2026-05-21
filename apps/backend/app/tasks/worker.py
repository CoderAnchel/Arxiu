"""ARQ worker entrypoint.

Phase 2 — wired with a no-op task so the worker container starts cleanly.
Phase 4 adds: generate_pdfs, send_emails. Phase 2 follow-up adds:
import_alumnes_excel.
"""
from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(level=settings.log_level)
    logger.info("arq_worker_started", extra={"env": settings.app_env})
    ctx["settings"] = settings


async def shutdown(_ctx: dict[str, Any]) -> None:
    logger.info("arq_worker_shutdown")


async def healthcheck(_ctx: dict[str, Any]) -> dict[str, str]:
    """No-op task — useful for verifying the queue from a smoke test."""
    return {"status": "ok"}


def _redis_settings() -> RedisSettings:
    """Translate REDIS_URL into ARQ's RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(get_settings().redis_url)
    return RedisSettings(
        host=parsed.hostname or "redis",
        port=parsed.port or 6379,
        database=int((parsed.path or "/0").lstrip("/") or 0),
        password=parsed.password,
    )


class WorkerSettings:
    functions = [healthcheck]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = _redis_settings()
    queue_name = "arxiu:default"
    max_jobs = 10
    job_timeout = 300
