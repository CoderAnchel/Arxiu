"""FastAPI application entry point.

Phase 0 wires only the health endpoint, CORS, structured logging, and the v1 router shell.
Subsequent phases register additional routers and middleware.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import (
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    install_exception_handlers,
)
from app.core.observability import init_prometheus, init_sentry
from app.core.rate_limit import init_rate_limiter
from app.db.session import get_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(level=settings.log_level)
    logger.info("arxiu_backend_starting", extra={"env": settings.app_env, "version": __version__})

    # Verify DB connectivity early — fail-fast on misconfig.
    try:
        engine = get_engine()
        async with engine.connect():
            pass
        logger.info("db_connection_ok")
    except Exception as exc:  # pragma: no cover — startup failure path
        logger.exception("db_connection_failed", extra={"error": str(exc)})
        raise

    yield

    logger.info("arxiu_backend_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        docs_url="/api/v1/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-request-id", "x-new-access-token"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)

    install_exception_handlers(app)
    init_rate_limiter(app)
    init_sentry()
    init_prometheus(app)

    # Health endpoint (outside /api/v1, used by Docker healthcheck and load balancers)
    @app.get("/healthz", tags=["meta"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "env": settings.app_env}

    @app.get("/", tags=["meta"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": __version__, "docs": "/api/v1/docs"}

    app.include_router(v1_router)

    return app


app = create_app()
