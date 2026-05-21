"""Pedagogic statistics endpoints — distribution of grades, RA-level summary."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.v1.deps import CurrentUser, DbSession
from app.core import permissions
from app.core.exceptions import ArxiuError
from app.services import qualificacions, stats

router = APIRouter(prefix="/stats", tags=["stats"])


class HistogramBin(BaseModel):
    label: str
    lo: float
    hi: float
    count: int


class RaStat(BaseModel):
    ra_id: int
    codi: str
    descripcio: str
    pes: float
    avg: float | None
    suspesos: int
    aprovats: int
    no_qualificats: int


class ModulStatsResponse(BaseModel):
    modul_id: int
    grup_id: int
    avaluacio_id: int
    n_alumnes: int
    n_qualificats: int
    n_complerts: int
    avg_final: float | None
    median_final: float | None
    pct_aprovats: float | None
    histogram: list[HistogramBin]
    ras: list[RaStat]


@router.get(
    "/grup/{grup_id}/modul/{modul_id}/avaluacio/{avaluacio_id}",
    response_model=ModulStatsResponse,
)
async def get_modul_stats(
    grup_id: int,
    modul_id: int,
    avaluacio_id: int,
    db: DbSession,
    actor: CurrentUser,
):
    # Same permission rule as the grade matrix view
    if not permissions.is_admin(actor):
        has_assig = await qualificacions._has_assignacio(  # type: ignore[attr-defined]
            db,
            user_id=actor.id,
            grup_id=grup_id,
            modul_id=modul_id,
            curs_acad_id=0,  # checked below
        )
        is_tutor = await qualificacions._is_tutor_of_grup(  # type: ignore[attr-defined]
            db, user_id=actor.id, grup_id=grup_id
        )
        if not (has_assig or is_tutor):
            raise HTTPException(403, "permission_denied")

    try:
        result = await stats.compute_modul_stats(
            db, grup_id=grup_id, modul_id=modul_id, avaluacio_id=avaluacio_id
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return ModulStatsResponse(
        modul_id=result.modul_id,
        grup_id=result.grup_id,
        avaluacio_id=result.avaluacio_id,
        n_alumnes=result.n_alumnes,
        n_qualificats=result.n_qualificats,
        n_complerts=result.n_complerts,
        avg_final=result.avg_final,
        median_final=result.median_final,
        pct_aprovats=result.pct_aprovats,
        histogram=[HistogramBin(**asdict(b)) for b in result.histogram],
        ras=[RaStat(**asdict(r)) for r in result.ras],
    )
