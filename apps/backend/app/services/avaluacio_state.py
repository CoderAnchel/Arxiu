"""Avaluació state machine.

Strict transitions:
    oberta  → docent
    docent  → junta
    junta   → tancada

Admin override (rollback): admin may step back one state at a time
(`docent → oberta`, `junta → docent`, `tancada → junta`) for corrections.

Anyone-but-admin trying to transition gets PermissionDenied.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions
from app.core.exceptions import Conflict, NotFound, PermissionDenied
from app.models.grading import Avaluacio, EstatAvaluacio
from app.models.user import User
from app.services import audit

FORWARD_TRANSITIONS: dict[EstatAvaluacio, EstatAvaluacio] = {
    EstatAvaluacio.OBERTA: EstatAvaluacio.DOCENT,
    EstatAvaluacio.DOCENT: EstatAvaluacio.JUNTA,
    EstatAvaluacio.JUNTA: EstatAvaluacio.TANCADA,
}

BACKWARD_TRANSITIONS: dict[EstatAvaluacio, EstatAvaluacio] = {
    EstatAvaluacio.DOCENT: EstatAvaluacio.OBERTA,
    EstatAvaluacio.JUNTA: EstatAvaluacio.DOCENT,
    EstatAvaluacio.TANCADA: EstatAvaluacio.JUNTA,
}


def is_valid_transition(*, current: EstatAvaluacio, target: EstatAvaluacio) -> bool:
    return FORWARD_TRANSITIONS.get(current) == target or BACKWARD_TRANSITIONS.get(current) == target


def is_rollback(*, current: EstatAvaluacio, target: EstatAvaluacio) -> bool:
    return BACKWARD_TRANSITIONS.get(current) == target


async def get_avaluacio(session: AsyncSession, avaluacio_id: int) -> Avaluacio:
    aval = await session.get(Avaluacio, avaluacio_id)
    if aval is None or aval.deleted_at is not None:
        raise NotFound("avaluacio not found")
    return aval


async def transition(
    session: AsyncSession,
    *,
    avaluacio_id: int,
    target: EstatAvaluacio,
    actor: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Avaluacio:
    if not permissions.can_transition_avaluacio(actor):
        raise PermissionDenied()

    aval = await get_avaluacio(session, avaluacio_id)
    current = aval.estat

    if current == target:
        raise Conflict(f"avaluació already in state '{target}'")

    if not is_valid_transition(current=current, target=target):
        raise Conflict(
            f"invalid transition '{current.value}' → '{target.value}'",
            detail={"allowed_forward": FORWARD_TRANSITIONS.get(current),
                    "allowed_backward": BACKWARD_TRANSITIONS.get(current)},
        )

    rollback = is_rollback(current=current, target=target)

    before = {"estat": current.value}
    aval.estat = target

    if target == EstatAvaluacio.TANCADA:
        aval.data_tancament = date.today()
    elif target == EstatAvaluacio.OBERTA and aval.data_inici is None:
        aval.data_inici = date.today()
    elif target != EstatAvaluacio.TANCADA and rollback:
        # If rolling back from tancada, clear data_tancament
        if current == EstatAvaluacio.TANCADA:
            aval.data_tancament = None

    await session.flush()

    await audit.record(
        session,
        action="avaluacio_transition" + ("_rollback" if rollback else ""),
        entity="avaluacio",
        entity_id=aval.id,
        user_id=actor.id,
        before=before,
        after={"estat": target.value},
        ip=ip,
        user_agent=user_agent,
    )
    return aval
