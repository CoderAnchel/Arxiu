"""API v1 router aggregator."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    acta,
    admin_users,
    app_settings,
    archive,
    audit,
    auth,
    butlletins,
    catalog,
    dashboard,
    enviaments,
    exports,
    grading,
    imports,
    people,
    stats,
    trash,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(admin_users.router)
router.include_router(catalog.router)
router.include_router(people.router)
router.include_router(grading.router)
router.include_router(butlletins.router)
router.include_router(enviaments.router)
router.include_router(imports.router)
router.include_router(audit.router)
router.include_router(dashboard.router)
router.include_router(archive.router)
router.include_router(exports.router)
router.include_router(trash.router)
router.include_router(stats.router)
router.include_router(acta.router)
router.include_router(app_settings.router)
