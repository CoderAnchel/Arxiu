"""Paperera — list and restore soft-deleted entities.

The archive is permanent: once something is soft-deleted, the data is still
there but hidden from active views. An admin can browse the paperera and
restore items to bring them back.

Supported kinds: alumne, cicle, modul, ra, grup, assignacio_docent, matricula.

Each list endpoint returns a uniform shape:
    { id, label, sub, deleted_at }
so the frontend can render them in a single table per kind.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.deps import AdminUser, DbSession, get_request_metadata
from app.models.catalog import Cicle, Modul, Ra
from app.models.people import (
    Alumne,
    AssignacioDocent,
    GrupClasse,
    Matricula,
)
from app.services import audit
from fastapi import Request

router = APIRouter(prefix="/trash", tags=["trash"])


class TrashItem(BaseModel):
    id: int
    label: str
    sub: str
    deleted_at: datetime | None
    deleted_by_user_id: int | None = None


KINDS = {
    "alumne": Alumne,
    "cicle": Cicle,
    "modul": Modul,
    "ra": Ra,
    "grup": GrupClasse,
    "matricula": Matricula,
    "assignacio_docent": AssignacioDocent,
}


def _format_item(kind: str, obj: Any) -> TrashItem:
    if kind == "alumne":
        return TrashItem(
            id=obj.id,
            label=f"{obj.cognoms}, {obj.nom}",
            sub=f"DNI {obj.dni or '—'} · RALC {obj.ralc}",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "cicle":
        return TrashItem(
            id=obj.id,
            label=f"{obj.codi} · {obj.nom}",
            sub=f"nivell {getattr(obj.nivell, 'value', obj.nivell)}",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "modul":
        return TrashItem(
            id=obj.id,
            label=f"{obj.codi} · {obj.nom}",
            sub=f"cicle #{obj.cicle_id} · {obj.curs}r curs",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "ra":
        return TrashItem(
            id=obj.id,
            label=f"{obj.codi}",
            sub=obj.descripcio[:80],
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "grup":
        return TrashItem(
            id=obj.id,
            label=obj.codi,
            sub=f"curs #{obj.curs_acad_id} · cicle #{obj.cicle_id} · {obj.curs}r",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "matricula":
        return TrashItem(
            id=obj.id,
            label=f"matrícula #{obj.id}",
            sub=f"alumne #{obj.alumne_id} · grup #{obj.grup_id}",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    if kind == "assignacio_docent":
        return TrashItem(
            id=obj.id,
            label=f"assignació #{obj.id}",
            sub=f"user #{obj.user_id} · grup #{obj.grup_id} · mòdul #{obj.modul_id}",
            deleted_at=obj.deleted_at,
            deleted_by_user_id=getattr(obj, "deleted_by_user_id", None),
        )
    raise ValueError(kind)


@router.get("", response_model=dict[str, list[TrashItem]])
async def list_trash(
    db: DbSession,
    _: AdminUser,
    kind: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
):
    """List soft-deleted items. If `kind` omitted, returns a map of all kinds."""
    kinds = [kind] if kind is not None else list(KINDS.keys())
    out: dict[str, list[TrashItem]] = {}
    for k in kinds:
        if k not in KINDS:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown kind '{k}'")
        Model = KINDS[k]
        rows = list(
            (
                await db.execute(
                    select(Model)
                    .where(Model.deleted_at.is_not(None))
                    .order_by(Model.deleted_at.desc())
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        out[k] = [_format_item(k, r) for r in rows]
    return out


@router.post("/{kind}/{item_id}/restore", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def restore_item(
    kind: str, item_id: int, request: Request, db: DbSession, actor: AdminUser
) -> None:
    """Clear `deleted_at` so the item becomes visible again. Audit-logged."""
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown kind '{kind}'")
    Model = KINDS[kind]
    obj = await db.get(Model, item_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if obj.deleted_at is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_deleted")

    before = {"deleted_at": obj.deleted_at.isoformat() if obj.deleted_at else None}
    obj.deleted_at = None
    if hasattr(obj, "deleted_by_user_id"):
        obj.deleted_by_user_id = None
    await db.flush()

    meta = get_request_metadata(request)
    await audit.record(
        db,
        action=f"{kind}_restored",
        entity=kind,
        entity_id=obj.id,
        user_id=actor.id,
        before=before,
        after={"deleted_at": None},
        **meta,
    )
