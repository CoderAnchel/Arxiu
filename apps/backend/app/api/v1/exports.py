"""XLSX/CSV export endpoints.

Permission model:
- Admins can export anything.
- Professors can export:
  - their own docent fitxa (`/export/docent/me`)
  - any grup they are tutor of (full grup workbook)
  - any (grup, modul) combination they are assigned to (single-modul workbook)
  - their own alumnes (those who are matriculated in a grup they teach/tutor)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.v1.deps import AdminUser, CurrentUser, DbSession
from app.core import permissions
from app.core.exceptions import ArxiuError
from app.models.people import AssignacioDocent, GrupClasse, Matricula
from app.services import exports

router = APIRouter(prefix="/export", tags=["exports"])


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_response(payload: tuple[bytes, str]) -> Response:
    data, filename = payload
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _csv_response(payload: tuple[bytes, str]) -> Response:
    data, filename = payload
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Permission helpers --------------------------------------------------


async def _professor_can_access_grup(
    db, *, user_id: int, grup_id: int
) -> bool:
    """A professor can access a grup if tutor OR has any assignacio in it."""
    g = await db.get(GrupClasse, grup_id)
    if g is None or g.deleted_at is not None:
        return False
    if g.tutor_user_id == user_id:
        return True
    has = (
        await db.execute(
            select(AssignacioDocent).where(
                AssignacioDocent.user_id == user_id,
                AssignacioDocent.grup_id == grup_id,
                AssignacioDocent.deleted_at.is_(None),
            )
        )
    ).scalars().first()
    return has is not None


async def _professor_can_access_alumne(
    db, *, user_id: int, alumne_id: int
) -> bool:
    """An alumne is accessible if matriculated in any grup the user has access to."""
    matricules = (
        await db.execute(
            select(Matricula).where(
                Matricula.alumne_id == alumne_id, Matricula.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    for m in matricules:
        if await _professor_can_access_grup(db, user_id=user_id, grup_id=m.grup_id):
            return True
    return False


# --- Endpoints -----------------------------------------------------------


@router.get("/alumne/{alumne_id}.xlsx")
async def export_alumne(alumne_id: int, db: DbSession, actor: CurrentUser):
    if not permissions.is_admin(actor):
        if not await _professor_can_access_alumne(db, user_id=actor.id, alumne_id=alumne_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
    try:
        return _xlsx_response(await exports.export_alumne(db, alumne_id))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/grup/{grup_id}.xlsx")
async def export_grup(grup_id: int, db: DbSession, actor: CurrentUser):
    if not permissions.is_admin(actor):
        if not await _professor_can_access_grup(db, user_id=actor.id, grup_id=grup_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
    try:
        return _xlsx_response(await exports.export_grup(db, grup_id))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/grup/{grup_id}/modul/{modul_id}.xlsx")
async def export_grup_modul(
    grup_id: int,
    modul_id: int,
    db: DbSession,
    actor: CurrentUser,
    avaluacio_id: int | None = Query(default=None),
):
    if not permissions.is_admin(actor):
        # Professor needs explicit assignacio for (grup, modul) OR tutorship
        ok = False
        if await _professor_can_access_grup(db, user_id=actor.id, grup_id=grup_id):
            has = (
                await db.execute(
                    select(AssignacioDocent).where(
                        AssignacioDocent.user_id == actor.id,
                        AssignacioDocent.grup_id == grup_id,
                        AssignacioDocent.modul_id == modul_id,
                        AssignacioDocent.deleted_at.is_(None),
                    )
                )
            ).scalars().first()
            g = await db.get(GrupClasse, grup_id)
            if has is not None or (g is not None and g.tutor_user_id == actor.id):
                ok = True
        if not ok:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
    try:
        return _xlsx_response(
            await exports.export_grup_modul(db, grup_id, modul_id, avaluacio_id)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/curs/{curs_id}.xlsx")
async def export_curs(curs_id: int, db: DbSession, _: AdminUser):
    try:
        return _xlsx_response(await exports.export_curs(db, curs_id))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/cicle/{cicle_id}.xlsx")
async def export_cicle(cicle_id: int, db: DbSession, _: CurrentUser):
    # Public to any authenticated user — cicle structure is non-sensitive
    try:
        return _xlsx_response(await exports.export_cicle(db, cicle_id))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/docent/{user_id}.xlsx")
async def export_docent(user_id: int, db: DbSession, actor: CurrentUser):
    # Admin can export anyone; professor can export own
    if not permissions.is_admin(actor) and actor.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
    try:
        return _xlsx_response(await exports.export_docent(db, user_id))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.get("/audit.csv")
async def export_audit(
    db: DbSession,
    _: AdminUser,
    user_id: int | None = Query(default=None),
    entity: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=5000, ge=1, le=50000),
):
    return _csv_response(
        await exports.export_audit_csv(
            db, user_id=user_id, entity=entity, action=action, limit=limit
        )
    )
