"""CRUD service for alumnes, grups, matrícules, assignacions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import Conflict, NotFound, ValidationError
from app.models.catalog import Cicle, CursAcademic, Modul
from app.models.people import (
    Alumne,
    AssignacioDocent,
    GrupClasse,
    Matricula,
    TutorLegal,
)
from app.models.user import User
from app.schemas.people import (
    AlumneCreate,
    AlumneUpdate,
    AssignacioDocentCreate,
    GrupClasseCreate,
    GrupClasseUpdate,
    MatriculaCreate,
    MatriculaUpdate,
    TutorLegalCreate,
)
from app.services import audit


async def _get_or_404(session: AsyncSession, model, pk: int, *, soft: bool = True):  # type: ignore[no-untyped-def]
    obj = await session.get(model, pk)
    if obj is None:
        raise NotFound(f"{model.__tablename__} not found")
    if soft and getattr(obj, "deleted_at", None) is not None:
        raise NotFound(f"{model.__tablename__} not found")
    return obj


# ---------------------------------------------------------------------------
# Alumnes
# ---------------------------------------------------------------------------

async def list_alumnes(
    session: AsyncSession,
    *,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_deleted: bool = False,
) -> list[Alumne]:
    stmt = select(Alumne).options(selectinload(Alumne.tutors_legals))
    if not include_deleted:
        stmt = stmt.where(Alumne.deleted_at.is_(None))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Alumne.nom.ilike(like),
                Alumne.cognoms.ilike(like),
                Alumne.dni.ilike(like),
                Alumne.ralc.ilike(like),
                Alumne.email.ilike(like),
            )
        )
    stmt = stmt.order_by(Alumne.cognoms, Alumne.nom).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().unique().all())


async def get_alumne(session: AsyncSession, alumne_id: int) -> Alumne:
    stmt = (
        select(Alumne)
        .where(Alumne.id == alumne_id, Alumne.deleted_at.is_(None))
        .options(selectinload(Alumne.tutors_legals))
    )
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise NotFound("alumne not found")
    return obj


async def create_alumne(
    session: AsyncSession, payload: AlumneCreate, *, actor_id: int, **meta: str | None
) -> Alumne:
    alumne = Alumne(
        dni=payload.dni.upper() if payload.dni else None,
        ralc=payload.ralc,
        nom=payload.nom,
        cognoms=payload.cognoms,
        email=str(payload.email).lower() if payload.email else None,
        telefon=payload.telefon,
        data_naixement=payload.data_naixement,
    )
    for tutor in payload.tutors_legals:
        alumne.tutors_legals.append(_tutor_from_payload(tutor))
    session.add(alumne)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("alumne amb aquest RALC ja existeix") from exc
    # Pre-load tutors_legals while still inside the async session greenlet so
    # FastAPI's response serializer doesn't trigger a lazy-load afterwards.
    await session.refresh(alumne, attribute_names=["tutors_legals"])
    await audit.record(
        session,
        action="alumne_created",
        entity="alumne",
        entity_id=alumne.id,
        user_id=actor_id,
        after={"dni": alumne.dni, "ralc": alumne.ralc, "nom": f"{alumne.cognoms}, {alumne.nom}"},
        **meta,
    )
    return alumne


def _tutor_from_payload(t: TutorLegalCreate) -> TutorLegal:
    return TutorLegal(
        nom=t.nom,
        email=str(t.email).lower() if t.email else None,
        telefon=t.telefon,
    )


async def update_alumne(
    session: AsyncSession,
    alumne_id: int,
    payload: AlumneUpdate,
    *,
    actor_id: int,
    **meta: str | None,
) -> Alumne:
    alumne = await get_alumne(session, alumne_id)
    before = {
        k: getattr(alumne, k)
        for k in ("dni", "ralc", "nom", "cognoms", "email", "telefon")
    }
    data = payload.model_dump(exclude_unset=True)
    if "dni" in data and data["dni"]:
        data["dni"] = data["dni"].upper()
    if "email" in data and data["email"]:
        data["email"] = str(data["email"]).lower()
    for k, v in data.items():
        setattr(alumne, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks uniqueness") from exc
    await audit.record(
        session,
        action="alumne_updated",
        entity="alumne",
        entity_id=alumne.id,
        user_id=actor_id,
        before=before,
        after={**before, **data},
        **meta,
    )
    return alumne


async def soft_delete_alumne(
    session: AsyncSession, alumne_id: int, *, actor_id: int, **meta: str | None
) -> None:
    alumne = await get_alumne(session, alumne_id)
    alumne.deleted_at = datetime.now(timezone.utc)
    alumne.deleted_by_user_id = actor_id
    await audit.record(
        session, action="alumne_soft_deleted", entity="alumne", entity_id=alumne.id,
        user_id=actor_id, **meta,
    )


# ---------------------------------------------------------------------------
# Grups classe
# ---------------------------------------------------------------------------

async def list_grups(
    session: AsyncSession, *, curs_acad_id: int | None = None
) -> list[GrupClasse]:
    stmt = select(GrupClasse).where(GrupClasse.deleted_at.is_(None))
    if curs_acad_id is not None:
        stmt = stmt.where(GrupClasse.curs_acad_id == curs_acad_id)
    stmt = stmt.order_by(GrupClasse.codi)
    return list((await session.execute(stmt)).scalars().unique().all())


async def get_grup(session: AsyncSession, grup_id: int) -> GrupClasse:
    stmt = (
        select(GrupClasse)
        .where(GrupClasse.id == grup_id, GrupClasse.deleted_at.is_(None))
    )
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise NotFound("grup not found")
    return obj


async def create_grup(
    session: AsyncSession, payload: GrupClasseCreate, *, actor_id: int, **meta: str | None
) -> GrupClasse:
    await _get_or_404(session, CursAcademic, payload.curs_acad_id, soft=False)
    await _get_or_404(session, Cicle, payload.cicle_id)
    if payload.tutor_user_id is not None:
        await _get_or_404(session, User, payload.tutor_user_id)
    grup = GrupClasse(**payload.model_dump())
    grup.codi = grup.codi.upper()
    session.add(grup)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("grup amb aquest codi ja existeix al curs") from exc
    await audit.record(
        session,
        action="grup_created",
        entity="grup_classe",
        entity_id=grup.id,
        user_id=actor_id,
        **meta,
    )
    return grup


async def update_grup(
    session: AsyncSession,
    grup_id: int,
    payload: GrupClasseUpdate,
    *,
    actor_id: int,
    **meta: str | None,
) -> GrupClasse:
    grup = await get_grup(session, grup_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(grup, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks uniqueness") from exc
    await audit.record(
        session,
        action="grup_updated",
        entity="grup_classe",
        entity_id=grup.id,
        user_id=actor_id,
        after=data,
        **meta,
    )
    return grup


# ---------------------------------------------------------------------------
# Matrícules
# ---------------------------------------------------------------------------

async def list_matricules(
    session: AsyncSession,
    *,
    curs_acad_id: int | None = None,
    grup_id: int | None = None,
    alumne_id: int | None = None,
) -> list[Matricula]:
    stmt = select(Matricula).where(Matricula.deleted_at.is_(None))
    if curs_acad_id is not None:
        stmt = stmt.where(Matricula.curs_acad_id == curs_acad_id)
    if grup_id is not None:
        stmt = stmt.where(Matricula.grup_id == grup_id)
    if alumne_id is not None:
        stmt = stmt.where(Matricula.alumne_id == alumne_id)
    stmt = stmt.order_by(Matricula.curs_acad_id.desc(), Matricula.id)
    return list((await session.execute(stmt)).scalars().unique().all())


async def create_matricula(
    session: AsyncSession, payload: MatriculaCreate, *, actor_id: int, **meta: str | None
) -> Matricula:
    matr = Matricula(**payload.model_dump())
    session.add(matr)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("matrícula duplicada (alumne+curs+cicle ja existeix)") from exc
    await audit.record(
        session,
        action="matricula_created",
        entity="matricula",
        entity_id=matr.id,
        user_id=actor_id,
        **meta,
    )
    return matr


async def update_matricula(
    session: AsyncSession,
    matricula_id: int,
    payload: MatriculaUpdate,
    *,
    actor_id: int,
    **meta: str | None,
) -> Matricula:
    matr = await session.get(Matricula, matricula_id)
    if matr is None or matr.deleted_at is not None:
        raise NotFound("matricula not found")
    data = payload.model_dump(exclude_unset=True)
    before = {"grup_id": matr.grup_id, "estat": matr.estat.value}
    for k, v in data.items():
        setattr(matr, k, v)
    await session.flush()
    await audit.record(
        session,
        action="matricula_updated",
        entity="matricula",
        entity_id=matr.id,
        user_id=actor_id,
        before=before,
        after=data,
        **meta,
    )
    return matr


# ---------------------------------------------------------------------------
# Assignacions docents
# ---------------------------------------------------------------------------

async def list_assignacions(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    grup_id: int | None = None,
    curs_acad_id: int | None = None,
) -> list[AssignacioDocent]:
    stmt = select(AssignacioDocent).where(AssignacioDocent.deleted_at.is_(None))
    if user_id is not None:
        stmt = stmt.where(AssignacioDocent.user_id == user_id)
    if grup_id is not None:
        stmt = stmt.where(AssignacioDocent.grup_id == grup_id)
    if curs_acad_id is not None:
        stmt = stmt.where(AssignacioDocent.curs_acad_id == curs_acad_id)
    return list((await session.execute(stmt)).scalars().unique().all())


async def create_assignacio(
    session: AsyncSession, payload: AssignacioDocentCreate, *, actor_id: int, **meta: str | None
) -> AssignacioDocent:
    # Validate FKs exist
    await _get_or_404(session, User, payload.user_id)
    grup = await _get_or_404(session, GrupClasse, payload.grup_id)
    modul = await _get_or_404(session, Modul, payload.modul_id)
    await _get_or_404(session, CursAcademic, payload.curs_acad_id, soft=False)

    # A group of 1r curs can't be assigned a 2n-curs module of the cicle, and
    # vice-versa: each module belongs to a specific year of the cicle.
    if grup.curs != modul.curs:
        raise ValidationError(
            f"mòdul de {modul.curs}r curs no es pot assignar a grup de {grup.curs}r curs"
        )
    if grup.cicle_id != modul.cicle_id:
        raise ValidationError("mòdul i grup pertanyen a cicles diferents")

    a = AssignacioDocent(**payload.model_dump())
    session.add(a)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("assignació duplicada") from exc
    await audit.record(
        session,
        action="assignacio_created",
        entity="assignacio_docent",
        entity_id=a.id,
        user_id=actor_id,
        **meta,
    )
    return a


async def soft_delete_assignacio(
    session: AsyncSession, assignacio_id: int, *, actor_id: int, **meta: str | None
) -> None:
    a = await session.get(AssignacioDocent, assignacio_id)
    if a is None or a.deleted_at is not None:
        raise NotFound("assignacio not found")
    a.deleted_at = datetime.now(timezone.utc)
    a.deleted_by_user_id = actor_id
    await audit.record(
        session,
        action="assignacio_soft_deleted",
        entity="assignacio_docent",
        entity_id=a.id,
        user_id=actor_id,
        **meta,
    )
