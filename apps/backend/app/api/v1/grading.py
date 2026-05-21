"""Avaluacions + qualificacions endpoints."""
from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import select

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.v1.deps import AdminUser, CurrentUser, DbSession, get_request_metadata
from app.core import permissions
from app.core.exceptions import ArxiuError
from app.models.grading import Avaluacio
from app.models.people import GrupClasse
from app.schemas.grading import (
    AvaluacioCreate,
    AvaluacioResponse,
    AvaluacioTransitionRequest,
    BulkQualifModulPatch,
    BulkQualifModulPatchResponse,
    BulkQualifRaPatch,
    BulkQualifRaPatchResponse,
    GradeMatrixAlumne,
    GradeMatrixCell,
    GradeMatrixModulCell,
    GradeMatrixRa,
    GradeMatrixResponse,
    QualifModulPatchResult,
    QualifRaPatchResult,
)
from app.services import audit, avaluacio_state, qualificacions
from app.services.qualificacions import QualifModulPatch, QualifPatch

router = APIRouter(tags=["grading"])


# --- Avaluacions ------------------------------------------------------------

@router.get("/avaluacions", response_model=list[AvaluacioResponse])
async def list_avaluacions(
    db: DbSession,
    _: CurrentUser,
    curs_acad_id: int | None = Query(default=None),
):
    stmt = select(Avaluacio).where(Avaluacio.deleted_at.is_(None))
    if curs_acad_id is not None:
        stmt = stmt.where(Avaluacio.curs_acad_id == curs_acad_id)
    stmt = stmt.order_by(Avaluacio.curs_acad_id.desc(), Avaluacio.ordre)
    return list((await db.execute(stmt)).scalars().all())


@router.post(
    "/avaluacions", response_model=AvaluacioResponse, status_code=status.HTTP_201_CREATED
)
async def create_avaluacio(
    payload: AvaluacioCreate, request: Request, db: DbSession, actor: AdminUser
) -> Avaluacio:
    aval = Avaluacio(**payload.model_dump())
    db.add(aval)
    try:
        await db.flush()
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "conflict") from exc
    await audit.record(
        db,
        action="avaluacio_created",
        entity="avaluacio",
        entity_id=aval.id,
        user_id=actor.id,
        after={"nom": aval.nom, "ordre": aval.ordre},
        **get_request_metadata(request),
    )
    return aval


@router.post("/avaluacions/{avaluacio_id}/transition", response_model=AvaluacioResponse)
async def transition_avaluacio(
    avaluacio_id: int,
    payload: AvaluacioTransitionRequest,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    try:
        return await avaluacio_state.transition(
            db,
            avaluacio_id=avaluacio_id,
            target=payload.target,
            actor=actor,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code, headers={}) from exc


# --- Grade matrix (read) ----------------------------------------------------

@router.get("/qualificacions/ra", response_model=GradeMatrixResponse)
async def get_grade_matrix(
    db: DbSession,
    actor: CurrentUser,
    grup_id: int = Query(..., ge=1),
    modul_id: int = Query(..., ge=1),
    avaluacio_id: int = Query(..., ge=1),
):
    aval = await db.get(Avaluacio, avaluacio_id)
    if aval is None or aval.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "avaluacio_not_found")

    # Permission to view: admin, OR assigned to (grup,modul,curs), OR tutor of grup
    if not permissions.is_admin(actor):
        has_assig = await qualificacions._has_assignacio(  # type: ignore[attr-defined]
            db,
            user_id=actor.id,
            grup_id=grup_id,
            modul_id=modul_id,
            curs_acad_id=aval.curs_acad_id,
        )
        is_tutor = await qualificacions._is_tutor_of_grup(  # type: ignore[attr-defined]
            db, user_id=actor.id, grup_id=grup_id
        )
        if not permissions.can_view_qualifs_for_grup(
            user=actor, has_assignacio=has_assig, is_tutor_of_grup=is_tutor
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")
        can_edit_now = permissions.can_edit_qualif_ra(
            user=actor,
            avaluacio_estat=aval.estat.value,
            has_assignacio=has_assig,
            is_tutor_of_grup=is_tutor,
        )
    else:
        can_edit_now = True

    alumnes, ras, cells, modul_cells = await qualificacions.load_grade_matrix(
        db, grup_id=grup_id, modul_id=modul_id, avaluacio_id=avaluacio_id
    )

    grup = await db.get(GrupClasse, grup_id)
    if grup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "grup_not_found")

    return GradeMatrixResponse(
        grup_id=grup_id,
        modul_id=modul_id,
        avaluacio_id=avaluacio_id,
        avaluacio_estat=aval.estat,
        can_edit=can_edit_now,
        alumnes=[GradeMatrixAlumne(**asdict(a)) for a in alumnes],
        ras=[
            GradeMatrixRa(id=r.id, ordre=r.ordre, codi=r.codi, descripcio=r.descripcio, pes=r.pes)
            for r in ras
        ],
        cells=[GradeMatrixCell(**asdict(c)) for c in cells],
        modul_cells=[GradeMatrixModulCell(**asdict(c)) for c in modul_cells],
    )


# --- Bulk PATCH -------------------------------------------------------------

@router.patch("/qualificacions/ra/batch", response_model=BulkQualifRaPatchResponse)
async def batch_patch_qualif_ra(
    payload: BulkQualifRaPatch, request: Request, db: DbSession, actor: CurrentUser
) -> BulkQualifRaPatchResponse:
    try:
        results = await qualificacions.batch_upsert_ra(
            db,
            avaluacio_id=payload.avaluacio_id,
            patches=[
                QualifPatch(
                    matricula_id=p.matricula_id,
                    ra_id=p.ra_id,
                    nota=p.nota,
                    comentari=p.comentari,
                )
                for p in payload.patches
            ],
            actor=actor,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return BulkQualifRaPatchResponse(
        results=[QualifRaPatchResult(**asdict(r)) for r in results],
        saved=sum(1 for r in results if r.ok),
        failed=sum(1 for r in results if not r.ok),
    )


@router.patch("/qualificacions/modul/batch", response_model=BulkQualifModulPatchResponse)
async def batch_patch_qualif_modul(
    payload: BulkQualifModulPatch, request: Request, db: DbSession, actor: CurrentUser
) -> BulkQualifModulPatchResponse:
    """Manual modul-level override of the final nota (bypasses RA mean).

    A null nota means "remove override" — the spreadsheet returns to showing
    the computed RA mean as the final.
    """
    try:
        results = await qualificacions.batch_upsert_modul(
            db,
            avaluacio_id=payload.avaluacio_id,
            modul_id=payload.modul_id,
            patches=[
                QualifModulPatch(
                    matricula_id=p.matricula_id, nota=p.nota, comentari=p.comentari
                )
                for p in payload.patches
            ],
            actor=actor,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return BulkQualifModulPatchResponse(
        results=[QualifModulPatchResult(**asdict(r)) for r in results],
        saved=sum(1 for r in results if r.ok),
        failed=sum(1 for r in results if not r.ok),
    )
