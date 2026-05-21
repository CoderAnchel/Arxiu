"""Dashboard aggregations — counts and recent activity for the home page."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.v1.deps import CurrentUser, DbSession
from app.models.audit_log import AuditLog
from app.models.catalog import Cicle, CursAcademic
from app.models.grading import Avaluacio
from app.models.people import GrupClasse, Matricula

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class DashboardStats(BaseModel):
    curs_actiu_id: int | None
    curs_actiu_nom: str | None
    alumnes_matriculats: int
    grups_actius: int
    cicles_actius: int
    avaluacio_actual: str | None
    avaluacio_actual_estat: str | None
    pendents: int  # alumnes matriculats actius sense cap nota a l'avaluació actual


class ActivityRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    entity: str
    entity_id: str | None
    user_id: int | None
    created_at: datetime


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_activity: list[ActivityRow]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(db: DbSession, _: CurrentUser) -> DashboardResponse:
    # Curs actiu
    curs_stmt = select(CursAcademic).where(CursAcademic.actiu.is_(True)).limit(1)
    curs = (await db.execute(curs_stmt)).scalar_one_or_none()

    stats = DashboardStats(
        curs_actiu_id=curs.id if curs else None,
        curs_actiu_nom=curs.nom if curs else None,
        alumnes_matriculats=0,
        grups_actius=0,
        cicles_actius=0,
        avaluacio_actual=None,
        avaluacio_actual_estat=None,
        pendents=0,
    )

    if curs is not None:
        # Alumnes amb matrícula activa al curs
        stats.alumnes_matriculats = (
            await db.execute(
                select(func.count(Matricula.id)).where(
                    Matricula.curs_acad_id == curs.id,
                    Matricula.estat == "actiu",
                    Matricula.deleted_at.is_(None),
                )
            )
        ).scalar_one()

        # Grups actius
        stats.grups_actius = (
            await db.execute(
                select(func.count(GrupClasse.id)).where(
                    GrupClasse.curs_acad_id == curs.id,
                    GrupClasse.deleted_at.is_(None),
                )
            )
        ).scalar_one()

        # Cicles distints amb grups actius al curs
        stats.cicles_actius = (
            await db.execute(
                select(func.count(func.distinct(GrupClasse.cicle_id))).where(
                    GrupClasse.curs_acad_id == curs.id,
                    GrupClasse.deleted_at.is_(None),
                )
            )
        ).scalar_one()

        # Avaluació no-tancada amb ordre mínim
        aval_stmt = (
            select(Avaluacio)
            .where(
                Avaluacio.curs_acad_id == curs.id,
                Avaluacio.deleted_at.is_(None),
                Avaluacio.estat != "tancada",
            )
            .order_by(Avaluacio.ordre)
            .limit(1)
        )
        aval = (await db.execute(aval_stmt)).scalar_one_or_none()
        if aval is not None:
            stats.avaluacio_actual = aval.nom
            stats.avaluacio_actual_estat = aval.estat.value if hasattr(aval.estat, "value") else str(aval.estat)

    # Recent activity (últims 20 audit logs)
    activity_stmt = (
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(20)
    )
    activity = list((await db.execute(activity_stmt)).scalars().all())

    return DashboardResponse(
        stats=stats,
        recent_activity=[ActivityRow.model_validate(r) for r in activity],
    )


# Cicle exists check for completeness — used by overview's tree
@router.get("/tree", response_model=list[dict])
async def get_tree(db: DbSession, _: CurrentUser, curs_acad_id: int | None = None) -> list:
    """Returns the hierarchy: curs → cicle → grup. Lightweight for the home tree."""
    if curs_acad_id is None:
        curs = (
            await db.execute(select(CursAcademic).where(CursAcademic.actiu.is_(True)).limit(1))
        ).scalar_one_or_none()
        if curs is None:
            return []
        curs_acad_id = curs.id

    grups = list(
        (
            await db.execute(
                select(GrupClasse)
                .where(
                    GrupClasse.curs_acad_id == curs_acad_id,
                    GrupClasse.deleted_at.is_(None),
                )
                .order_by(GrupClasse.codi)
            )
        )
        .scalars()
        .all()
    )

    by_cicle: dict[int, list[dict]] = {}
    for g in grups:
        by_cicle.setdefault(g.cicle_id, []).append(
            {"id": g.id, "codi": g.codi, "curs": g.curs, "tutor_user_id": g.tutor_user_id}
        )

    cicle_ids = list(by_cicle.keys())
    if not cicle_ids:
        return []
    cicles = list(
        (
            await db.execute(
                select(Cicle).where(Cicle.id.in_(cicle_ids), Cicle.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "id": c.id,
            "codi": c.codi,
            "nom": c.nom,
            "nivell": c.nivell.value if hasattr(c.nivell, "value") else str(c.nivell),
            "grups": by_cicle.get(c.id, []),
        }
        for c in cicles
    ]
