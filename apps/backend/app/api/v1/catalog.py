"""Catalog endpoints — families, cicles, mòduls, RAs, cursos acadèmics. Admin-only writes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.v1.deps import AdminUser, CurrentUser, DbSession, get_request_metadata
from app.core.exceptions import ArxiuError
from app.schemas.catalog import (
    CicleCreate,
    CicleDetailResponse,
    CicleResponse,
    CicleUpdate,
    CursAcademicCloneRequest,
    CursAcademicCreate,
    CursAcademicResponse,
    CursAcademicUpdate,
    FamiliaCreate,
    FamiliaResponse,
    FamiliaUpdate,
    ModulCreate,
    ModulResponse,
    ModulUpdate,
    RaCreate,
    RaResponse,
    RaUpdate,
)
from app.services import catalog as svc

router = APIRouter(tags=["catalog"])


# --- Famílies ---------------------------------------------------------------

@router.get("/families", response_model=list[FamiliaResponse])
async def list_families(db: DbSession, _: CurrentUser) -> list:
    return await svc.list_families(db)


@router.post("/families", response_model=FamiliaResponse, status_code=status.HTTP_201_CREATED)
async def create_familia(
    payload: FamiliaCreate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.create_familia(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/families/{familia_id}", response_model=FamiliaResponse)
async def update_familia(
    familia_id: int,
    payload: FamiliaUpdate,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    try:
        return await svc.update_familia(
            db, familia_id, payload, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.delete(
    "/families/{familia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_familia(
    familia_id: int, request: Request, db: DbSession, actor: AdminUser
) -> None:
    try:
        await svc.soft_delete_familia(
            db, familia_id, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- Cicles -----------------------------------------------------------------

@router.get("/cicles", response_model=list[CicleResponse])
async def list_cicles(db: DbSession, _: CurrentUser) -> list:
    return await svc.list_cicles(db)


@router.get("/cicles/{cicle_id}", response_model=CicleDetailResponse)
async def get_cicle(cicle_id: int, db: DbSession, _: CurrentUser):
    try:
        return await svc.get_cicle(db, cicle_id, with_moduls=True)
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.post("/cicles", response_model=CicleResponse, status_code=status.HTTP_201_CREATED)
async def create_cicle(payload: CicleCreate, request: Request, db: DbSession, actor: AdminUser):
    try:
        return await svc.create_cicle(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/cicles/{cicle_id}", response_model=CicleResponse)
async def update_cicle(
    cicle_id: int, payload: CicleUpdate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.update_cicle(
            db, cicle_id, payload, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.delete(
    "/cicles/{cicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_cicle(cicle_id: int, request: Request, db: DbSession, actor: AdminUser) -> None:
    try:
        await svc.soft_delete_cicle(db, cicle_id, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- Mòduls -----------------------------------------------------------------

@router.get("/moduls", response_model=list[ModulResponse])
async def list_moduls(
    db: DbSession,
    _: CurrentUser,
    cicle_id: int | None = Query(default=None),
):
    return await svc.list_moduls(db, cicle_id=cicle_id)


@router.post("/moduls", response_model=ModulResponse, status_code=status.HTTP_201_CREATED)
async def create_modul(payload: ModulCreate, request: Request, db: DbSession, actor: AdminUser):
    try:
        return await svc.create_modul(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/moduls/{modul_id}", response_model=ModulResponse)
async def update_modul(
    modul_id: int, payload: ModulUpdate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.update_modul(
            db, modul_id, payload, actor_id=actor.id, **get_request_metadata(request)
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.delete(
    "/moduls/{modul_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_modul(modul_id: int, request: Request, db: DbSession, actor: AdminUser) -> None:
    try:
        await svc.soft_delete_modul(db, modul_id, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- RAs --------------------------------------------------------------------

@router.get("/moduls/{modul_id}/ras", response_model=list[RaResponse])
async def list_ras(modul_id: int, db: DbSession, _: CurrentUser):
    return await svc.list_ras(db, modul_id=modul_id)


@router.post("/ras", response_model=RaResponse, status_code=status.HTTP_201_CREATED)
async def create_ra(payload: RaCreate, request: Request, db: DbSession, actor: AdminUser):
    try:
        return await svc.create_ra(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/ras/{ra_id}", response_model=RaResponse)
async def update_ra(ra_id: int, payload: RaUpdate, request: Request, db: DbSession, actor: AdminUser):
    try:
        return await svc.update_ra(db, ra_id, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.delete(
    "/ras/{ra_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_ra(ra_id: int, request: Request, db: DbSession, actor: AdminUser) -> None:
    try:
        await svc.soft_delete_ra(db, ra_id, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# --- Cursos acadèmics -------------------------------------------------------

@router.get("/cursos-academics", response_model=list[CursAcademicResponse])
async def list_cursos(db: DbSession, _: CurrentUser):
    return await svc.list_cursos(db)


@router.get("/cursos-academics/active", response_model=CursAcademicResponse | None)
async def get_curs_actiu(db: DbSession, _: CurrentUser):
    return await svc.get_curs_actiu(db)


@router.post(
    "/cursos-academics", response_model=CursAcademicResponse, status_code=status.HTTP_201_CREATED
)
async def create_curs(
    payload: CursAcademicCreate, request: Request, db: DbSession, actor: AdminUser
):
    try:
        return await svc.create_curs(db, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.patch("/cursos-academics/{curs_id}", response_model=CursAcademicResponse)
async def update_curs(
    curs_id: int,
    payload: CursAcademicUpdate,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    try:
        return await svc.update_curs(db, curs_id, payload, actor_id=actor.id, **get_request_metadata(request))
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


@router.post(
    "/cursos-academics/{source_id}/clone",
    response_model=CursAcademicResponse,
    status_code=status.HTTP_201_CREATED,
)
async def clone_curs(
    source_id: int,
    payload: CursAcademicCloneRequest,
    request: Request,
    db: DbSession,
    actor: AdminUser,
):
    """Initialise a new curs acadèmic from the structure of an existing one.

    Clones grups (with same codis, cicle, curs, tutor) and optionally the
    assignacions docents to the new curs. Matrícules and notes are never
    cloned — alumnes change every year and each curs has its own state.
    """
    try:
        return await svc.clone_curs_academic(
            db,
            source_id,
            nom=payload.nom,
            actor_id=actor.id,
            set_active=payload.set_active,
            clone_grups=payload.clone_grups,
            clone_assignacions=payload.clone_assignacions,
            data_inici=payload.data_inici.isoformat() if payload.data_inici else None,
            data_fi=payload.data_fi.isoformat() if payload.data_fi else None,
            **get_request_metadata(request),
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
