"""Acta de Junta d'Avaluació — PDF endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core import permissions
from app.core.exceptions import ArxiuError
from app.models.people import AssignacioDocent, GrupClasse
from app.services import acta as acta_service
from sqlalchemy import select

router = APIRouter(tags=["acta"])


@router.get("/acta/grup/{grup_id}/avaluacio/{avaluacio_id}.pdf")
async def get_acta_pdf(
    grup_id: int,
    avaluacio_id: int,
    db: DbSession,
    actor: CurrentUser,
    tutor_signat: str | None = Query(default=None, max_length=200),
    cap_estudis_signat: str | None = Query(default=None, max_length=200),
    director_signat: str | None = Query(default=None, max_length=200),
) -> Response:
    # Permissions: admin everywhere; otherwise tutor of grup OR any docent
    # assigned to the grup.
    if not permissions.is_admin(actor):
        grup = await db.get(GrupClasse, grup_id)
        is_tutor = grup is not None and grup.tutor_user_id == actor.id
        has_assig = (
            await db.execute(
                select(AssignacioDocent).where(
                    AssignacioDocent.user_id == actor.id,
                    AssignacioDocent.grup_id == grup_id,
                    AssignacioDocent.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if not is_tutor and has_assig is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")

    try:
        pdf = await acta_service.render_acta_pdf(
            db,
            grup_id=grup_id,
            avaluacio_id=avaluacio_id,
            tutor_signat=tutor_signat,
            cap_estudis_signat=cap_estudis_signat,
            director_signat=director_signat,
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    filename = f"acta_{grup_id}_aval_{avaluacio_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
