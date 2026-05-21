"""Enviaments listing + resend."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.v1.deps import CurrentUser, DbSession, get_request_metadata
from app.core import permissions
from app.models.enviaments import Enviament, EstatEnviament
from app.schemas.outputs import EnviamentResponse
from app.services import audit
from app.services.butlleti import render_butlleti_email, render_butlleti_pdf
from app.services.email import send_butlleti

router = APIRouter(prefix="/enviaments", tags=["outputs"])


@router.get("", response_model=list[EnviamentResponse])
async def list_enviaments(
    db: DbSession,
    _: CurrentUser,
    estat: str | None = Query(default=None),
    alumne_id: int | None = Query(default=None),
    avaluacio_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Enviament)
    if estat:
        stmt = stmt.where(Enviament.estat == estat)
    if alumne_id is not None:
        stmt = stmt.where(Enviament.alumne_id == alumne_id)
    if avaluacio_id is not None:
        stmt = stmt.where(Enviament.avaluacio_id == avaluacio_id)
    stmt = stmt.order_by(Enviament.queued_at.desc()).limit(limit).offset(offset)
    rows = list((await db.execute(stmt)).scalars().all())
    return rows


@router.get("/{enviament_id}", response_model=EnviamentResponse)
async def get_enviament(
    enviament_id: int,
    db: DbSession,
    _: CurrentUser,
):
    env = await db.get(Enviament, enviament_id)
    if env is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "enviament_not_found")
    return env


@router.post("/{enviament_id}/resend", response_model=EnviamentResponse)
async def resend_enviament(
    enviament_id: int,
    request: Request,
    db: DbSession,
    actor: CurrentUser,
):
    """Re-render the butlletí + retry sending. Only for `error` or `rebotat` rows."""
    if not permissions.is_admin(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "permission_denied")

    env = await db.get(Enviament, enviament_id)
    if env is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "enviament_not_found")
    if env.estat not in (EstatEnviament.ERROR, EstatEnviament.REBOTAT):
        raise HTTPException(status.HTTP_409_CONFLICT, "not_resendable")
    if env.alumne_id is None or env.avaluacio_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "missing_source_data")

    pdf = await render_butlleti_pdf(db, alumne_id=env.alumne_id, avaluacio_id=env.avaluacio_id)
    html = render_butlleti_email(
        assumpte=env.assumpte,
        alumne_nom_complet=f"{env.alumne.nom} {env.alumne.cognoms}" if env.alumne else "",
        grup_codi="",
        avaluacio_nom="",
        curs_acad_nom="",
    )

    env.queued_at = datetime.now(timezone.utc)
    env.error_msg = None
    env.estat = EstatEnviament.QUEUED

    await send_butlleti(
        session=db,
        enviament=env,
        pdf_bytes=pdf,
        plain_body=f"Reenviament del butlletí: {env.assumpte}",
        html_body=html,
    )

    await audit.record(
        db,
        action="enviament_resent",
        entity="enviament",
        entity_id=env.id,
        user_id=actor.id,
        after={"estat": env.estat.value},
        **get_request_metadata(request),
    )
    return env
