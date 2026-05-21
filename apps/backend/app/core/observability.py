"""Sentry + Prometheus integrations. Call `init_observability(app)` once at startup."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def init_sentry() -> None:
    settings = get_settings()
    if not settings.sentry_dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:  # pragma: no cover
        logger.warning("sentry_sdk not installed; skipping init")
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.05,
        send_default_pii=False,
    )
    logger.info("sentry_initialised", extra={"env": settings.app_env})


def init_prometheus(app: FastAPI) -> None:
    """Mount /metrics with the prometheus_client default registry. Admin-restricted."""
    settings = get_settings()
    if not settings.prometheus_enabled:
        return
    try:
        from prometheus_client import (
            CONTENT_TYPE_LATEST,
            CollectorRegistry,
            Counter,
            Histogram,
            generate_latest,
            multiprocess,
        )
    except ImportError:  # pragma: no cover
        logger.warning("prometheus_client not installed; skipping init")
        return

    # Per-request counter + latency histogram
    req_counter = Counter(
        "arxiu_http_requests_total",
        "HTTP requests by method+route+status",
        ["method", "route", "status"],
    )
    req_latency = Histogram(
        "arxiu_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "route"],
        buckets=(0.005, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )

    @app.middleware("http")
    async def _prom_middleware(request, call_next):  # type: ignore[no-untyped-def]
        import time

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        req_counter.labels(request.method, path, str(response.status_code)).inc()
        req_latency.labels(request.method, path).observe(elapsed)
        return response

    @app.get("/metrics", include_in_schema=False, tags=["meta"])
    async def metrics() -> Response:
        # Fast-path: single-process registry. For multi-worker, switch to
        # multiprocess.MultiProcessCollector(registry).
        registry = CollectorRegistry()
        try:
            multiprocess.MultiProcessCollector(registry)  # type: ignore[arg-type]
        except Exception:
            from prometheus_client import REGISTRY

            registry = REGISTRY
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    logger.info("prometheus_mounted")
