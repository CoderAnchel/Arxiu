"""Endpoints for alumnes, grups, matrícules, assignacions."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.v1.deps import AdminUser, CurrentUser, DbSession, get_request_metadata
from app.core.exceptions import ArxiuError
from app.schemas.people import (
    AlumneCreate,
    AlumneResponse,
    AlumneUpdate,
    AssignacioDocentCreate,
    AssignacioDocentResponse,
    GrupClasseCreate,
    GrupClasseResponse,
    GrupClasseUpdate,
    MatriculaCreate,
    MatriculaResponse,
    MatriculaUpdate,
)
from app.services import people as svc

router = APIRouter(tags=["people"])


# --- Alumnes ----------------------------------------------------------------

@router.get("/alumnes", response_model=list[AlumneResponse])
async def list_alumnes(
    db: DbSession,
    _: CurrentUser,
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await svc.list_alumnes(db, q=q, limit=limit, offset=offset)


@router.get("/alumnes/{alumne_id}", response_model=AlumneResponse)
async def get_alumne(alumne_id: int, db: DbSession, _: CurrentUser):
    try:
        return await svc.get_alumne(db, alumne_id)
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.post("/alumnes", response_model=AlumneResponse, status_code=status.HTTP_201_CREATED)
async def create_alumne(payload: AlumneCreate, request: Request, db: DbSession, actor: AdminUser):
    try:
        return await svc.create_alumne(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/alumnes/{alumne_id}", response_model=AlumneResponse)
async def update_alumne(
    alumne_id: int, payload: AlumneUpdate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.update_alumne(
            db, alumne_id, payload, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.delete(
    "/alumnes/{alumne_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_alumne(alumne_id: int, request: Request, db: DbSession, actor: AdminUser) -> None:
    try:
        await svc.soft_delete_alumne(db, alumne_id, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- Grups ------------------------------------------------------------------

@router.get("/grups", response_model=list[GrupClasseResponse])
async def list_grups(
    db: DbSession,
    _: CurrentUser,
    curs_acad_id: int | None = Query(default=None),
):
    grups = await svc.list_grups(db, curs_acad_id=curs_acad_id)
    out = []
    for g in grups:
        out.append(
            GrupClasseResponse(
                id=g.id,
                codi=g.codi,
                curs_acad_id=g.curs_acad_id,
                cicle_id=g.cicle_id,
                curs=g.curs,
                tutor_user_id=g.tutor_user_id,
                cicle_codi=g.cicle.codi if g.cicle else None,
                curs_acad_nom=g.curs_acad.nom if g.curs_acad else None,
                tutor_nom_complet=(
                    f"{g.tutor.nom} {g.tutor.cognoms}" if g.tutor else None
                ),
            )
        )
    return out


@router.post("/grups", response_model=GrupClasseResponse, status_code=status.HTTP_201_CREATED)
async def create_grup(payload: GrupClasseCreate, request: Request, db: DbSession, actor: AdminUser):
    try:
        g = await svc.create_grup(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
    return GrupClasseResponse(
        id=g.id,
        codi=g.codi,
        curs_acad_id=g.curs_acad_id,
        cicle_id=g.cicle_id,
        curs=g.curs,
        tutor_user_id=g.tutor_user_id,
    )


@router.patch("/grups/{grup_id}", response_model=GrupClasseResponse)
async def update_grup(
    grup_id: int, payload: GrupClasseUpdate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        g = await svc.update_grup(db, grup_id, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
    return GrupClasseResponse(
        id=g.id,
        codi=g.codi,
        curs_acad_id=g.curs_acad_id,
        cicle_id=g.cicle_id,
        curs=g.curs,
        tutor_user_id=g.tutor_user_id,
    )


# --- Matrícules -------------------------------------------------------------

@router.get("/matricules", response_model=list[MatriculaResponse])
async def list_matricules(
    db: DbSession,
    _: CurrentUser,
    curs_acad_id: int | None = Query(default=None),
    grup_id: int | None = Query(default=None),
    alumne_id: int | None = Query(default=None),
):
    return await svc.list_matricules(
        db, curs_acad_id=curs_acad_id, grup_id=grup_id, alumne_id=alumne_id
    )


@router.post("/matricules", response_model=MatriculaResponse, status_code=status.HTTP_201_CREATED)
async def create_matricula(
    payload: MatriculaCreate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.create_matricula(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/matricules/{matricula_id}", response_model=MatriculaResponse)
async def update_matricula(
    matricula_id: int,
    payload: MatriculaUpdate,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    try:
        return await svc.update_matricula(
            db, matricula_id, payload, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- Assignacions docents ---------------------------------------------------

@router.get("/assignacions-docents", response_model=list[AssignacioDocentResponse])
async def list_assignacions(
    db: DbSession,
    _: CurrentUser,
    user_id: int | None = Query(default=None),
    grup_id: int | None = Query(default=None),
    curs_acad_id: int | None = Query(default=None),
):
    return await svc.list_assignacions(
        db, user_id=user_id, grup_id=grup_id, curs_acad_id=curs_acad_id
    )


@router.post(
    "/assignacions-docents",
    response_model=AssignacioDocentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignacio(
    payload: AssignacioDocentCreate, request: Request, db: DbSession, actor: AdminUser
):
    return await svc.create_assignacio(
        db, payload, actor_id=actor.id, **get_request_metadata(request)
    )


@router.delete(
    "/assignacions-docents/{assignacio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_assignacio(
    assignacio_id: int, request: Request, db: DbSession, actor: AdminUser
) -> None:
    try:
        await svc.soft_delete_assignacio(
            db, assignacio_id, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
