"""Imports endpoints (admin-only)."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy import select

from app.api.v1.deps import AdminUser, DbSession, get_request_metadata
from app.core.exceptions import ArxiuError
from app.models.imports import Import, TipusImport
from app.schemas.imports import (
    ImportConfirmResponse,
    ImportPreviewResponse,
    ImportPreviewRow,
    ImportResponse,
)
from app.services import imports as svc

router = APIRouter(prefix="/imports", tags=["imports"])


def _to_preview(imp: Import) -> ImportPreviewResponse:
    log = imp.log or {}
    preview = log.get("preview", [])
    return ImportPreviewResponse(
        id=imp.id,
        tipus=imp.tipus,
        fitxer_nom=imp.fitxer_nom,
        user_id=imp.user_id,
        total=imp.total,
        ok=imp.ok,
        errors=imp.errors,
        estat=imp.estat,
        created_at=imp.created_at,
        completed_at=imp.completed_at,
        preview=[ImportPreviewRow(**row) for row in preview],
    )


@router.get("", response_model=list[ImportResponse])
async def list_imports(
    db: DbSession,
    _: AdminUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = (
        select(Import)
        .order_by(Import.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


@router.get("/{import_id}", response_model=ImportPreviewResponse)
async def get_import(import_id: int, db: DbSession, _: AdminUser):
    imp = await db.get(Import, import_id)
    if imp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "import_not_found")
    return _to_preview(imp)


@router.post(
    "/alumnes",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_alumnes_import(
    request: Request,
    db: DbSession,
    actor: AdminUser,
    file: UploadFile = File(...),
):
    content = await file.read()
    try:
        imp, _rows = await svc.create_import_preview(
            db,
            tipus=TipusImport.ALUMNES,
            filename=file.filename or "alumnes.xlsx",
            content=content,
            actor_id=actor.id,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code, headers={}) from exc

    return _to_preview(imp)


@router.post("/{import_id}/confirm", response_model=ImportConfirmResponse)
async def confirm_import(
    import_id: int,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    try:
        imp = await svc.confirm_import(
            db,
            import_id=import_id,
            actor_id=actor.id,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return ImportConfirmResponse(
        id=imp.id,
        tipus=imp.tipus,
        fitxer_nom=imp.fitxer_nom,
        user_id=imp.user_id,
        total=imp.total,
        ok=imp.ok,
        errors=imp.errors,
        estat=imp.estat,
        created_at=imp.created_at,
        completed_at=imp.completed_at,
        result=(imp.log or {}).get("result"),
    )


@router.post(
    "/notes",
    response_model=ImportPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_notes_import(
    request: Request,
    db: DbSession,
    actor: AdminUser,
    modul_id: int = Form(...),
    avaluacio_id: int = Form(...),
    file: UploadFile = File(...),
):
    """Upload a notes file for a specific (mòdul, avaluació).
    Columns: identifier (DNI or RALC) + one per RA (header = RA codi or "RA1"…)."""
    content = await file.read()
    try:
        imp, _rows = await svc.create_import_preview(
            db,
            tipus=TipusImport.NOTES,
            filename=file.filename or "notes.xlsx",
            content=content,
            actor_id=actor.id,
            modul_id=modul_id,
            avaluacio_id=avaluacio_id,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return _to_preview(imp)
