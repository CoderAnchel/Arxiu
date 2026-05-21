"""CRUD service for catalog entities — families, cicles, mòduls, RAs, cursos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import Conflict, NotFound
from app.models.catalog import Cicle, CursAcademic, FamiliaProfessional, Modul, Ra
from app.schemas.catalog import (
    CicleCreate,
    CicleUpdate,
    CursAcademicCreate,
    CursAcademicUpdate,
    FamiliaCreate,
    FamiliaUpdate,
    ModulCreate,
    ModulUpdate,
    RaCreate,
    RaUpdate,
)
from app.services import audit

T = TypeVar("T")


def _strip_unset(payload) -> dict:  # type: ignore[no-untyped-def]
    return payload.model_dump(exclude_unset=True)


async def _get_or_404(session: AsyncSession, model: type[T], pk: int, *, soft: bool = True) -> T:
    obj = await session.get(model, pk)
    if obj is None:
        raise NotFound(f"{model.__tablename__} not found")
    if soft and getattr(obj, "deleted_at", None) is not None:
        raise NotFound(f"{model.__tablename__} not found")
    return obj


async def _get_modul_with_ras(session: AsyncSession, modul_id: int) -> Modul:
    stmt = (
        select(Modul)
        .where(Modul.id == modul_id, Modul.deleted_at.is_(None))
        .options(selectinload(Modul.ras))
    )
    modul = (await session.execute(stmt)).scalar_one_or_none()
    if modul is None:
        raise NotFound("modul not found")
    return modul


# --- Famílies ---------------------------------------------------------------

async def list_families(session: AsyncSession) -> list[FamiliaProfessional]:
    stmt = select(FamiliaProfessional).where(FamiliaProfessional.deleted_at.is_(None)).order_by(FamiliaProfessional.nom)
    return list((await session.execute(stmt)).scalars().all())


async def create_familia(
    session: AsyncSession, payload: FamiliaCreate, *, actor_id: int, **meta: str | None
) -> FamiliaProfessional:
    fam = FamiliaProfessional(codi=payload.codi.upper(), nom=payload.nom)
    session.add(fam)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("família amb aquest codi ja existeix") from exc
    await audit.record(
        session, action="familia_created", entity="familia", entity_id=fam.id, user_id=actor_id, **meta
    )
    return fam


async def update_familia(
    session: AsyncSession,
    familia_id: int,
    payload: FamiliaUpdate,
    *,
    actor_id: int,
    **meta: str | None,
) -> FamiliaProfessional:
    fam = await session.get(FamiliaProfessional, familia_id)
    if fam is None or fam.deleted_at is not None:
        raise NotFound("familia not found")
    before = {"codi": fam.codi, "nom": fam.nom}
    if payload.codi is not None:
        fam.codi = payload.codi.upper()
    if payload.nom is not None:
        fam.nom = payload.nom
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("família amb aquest codi ja existeix") from exc
    await audit.record(
        session,
        action="familia_updated",
        entity="familia",
        entity_id=fam.id,
        user_id=actor_id,
        before=before,
        after={"codi": fam.codi, "nom": fam.nom},
        **meta,
    )
    return fam


async def clone_curs_academic(
    session: AsyncSession,
    source_id: int,
    *,
    nom: str,
    actor_id: int,
    set_active: bool = False,
    clone_grups: bool = True,
    clone_assignacions: bool = True,
    data_inici: str | None = None,
    data_fi: str | None = None,
    **meta: str | None,
) -> CursAcademic:
    """Create a new curs acadèmic seeded with the structure of `source_id`.

    Clones: grups (with same codis + cicle + curs + tutor) and optionally
    assignacions docents. Does NOT clone: matrícules (alumnes change each year),
    avaluacions (each curs has its own state machine), notes (obviously).
    """
    from datetime import date as _date

    source = await session.get(CursAcademic, source_id)
    if source is None:
        raise NotFound("source curs not found")

    # Lazy imports to avoid cyclic imports at module top
    from app.models.people import AssignacioDocent, GrupClasse

    # Check destination doesn't already exist
    existing = (
        await session.execute(select(CursAcademic).where(CursAcademic.nom == nom))
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(f"ja existeix un curs amb nom '{nom}'")

    # If we're setting the new one as active, deactivate any current active curs.
    if set_active:
        await session.execute(
            select(CursAcademic).where(CursAcademic.actiu.is_(True))
        )
        # Use direct update — simpler than per-row
        from sqlalchemy import update as _update

        await session.execute(
            _update(CursAcademic).where(CursAcademic.actiu.is_(True)).values(actiu=False)
        )

    new_curs = CursAcademic(
        nom=nom,
        actiu=set_active,
        data_inici=_date.fromisoformat(data_inici) if data_inici else None,
        data_fi=_date.fromisoformat(data_fi) if data_fi else None,
    )
    session.add(new_curs)
    await session.flush()

    grups_cloned = 0
    assignacions_cloned = 0
    old_grup_to_new: dict[int, int] = {}

    if clone_grups:
        old_grups = list(
            (
                await session.execute(
                    select(GrupClasse).where(
                        GrupClasse.curs_acad_id == source_id,
                        GrupClasse.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for g in old_grups:
            new_g = GrupClasse(
                codi=g.codi,
                curs_acad_id=new_curs.id,
                cicle_id=g.cicle_id,
                curs=g.curs,
                tutor_user_id=g.tutor_user_id,
            )
            session.add(new_g)
            await session.flush()
            old_grup_to_new[g.id] = new_g.id
            grups_cloned += 1

        if clone_assignacions:
            old_assigs = list(
                (
                    await session.execute(
                        select(AssignacioDocent).where(
                            AssignacioDocent.curs_acad_id == source_id,
                            AssignacioDocent.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for a in old_assigs:
                if a.grup_id not in old_grup_to_new:
                    continue
                session.add(
                    AssignacioDocent(
                        user_id=a.user_id,
                        grup_id=old_grup_to_new[a.grup_id],
                        modul_id=a.modul_id,
                        curs_acad_id=new_curs.id,
                    )
                )
                assignacions_cloned += 1

    await session.flush()
    await audit.record(
        session,
        action="curs_cloned",
        entity="curs_academic",
        entity_id=new_curs.id,
        user_id=actor_id,
        after={
            "source_id": source_id,
            "nom": nom,
            "grups_cloned": grups_cloned,
            "assignacions_cloned": assignacions_cloned,
        },
        **meta,
    )
    return new_curs


async def soft_delete_familia(
    session: AsyncSession, familia_id: int, *, actor_id: int, **meta: str | None
) -> None:
    fam = await session.get(FamiliaProfessional, familia_id)
    if fam is None or fam.deleted_at is not None:
        raise NotFound("familia not found")
    fam.deleted_at = datetime.now(timezone.utc)
    fam.deleted_by_user_id = actor_id
    await audit.record(
        session,
        action="familia_soft_deleted",
        entity="familia",
        entity_id=fam.id,
        user_id=actor_id,
        **meta,
    )


# --- Cicles -----------------------------------------------------------------

async def list_cicles(session: AsyncSession) -> list[Cicle]:
    stmt = (
        select(Cicle)
        .where(Cicle.deleted_at.is_(None))
        .order_by(Cicle.codi)
    )
    return list((await session.execute(stmt)).scalars().unique().all())


async def get_cicle(session: AsyncSession, cicle_id: int, *, with_moduls: bool = False) -> Cicle:
    if not with_moduls:
        cicle = await _get_or_404(session, Cicle, cicle_id)
        return cicle
    stmt = (
        select(Cicle)
        .where(Cicle.id == cicle_id, Cicle.deleted_at.is_(None))
        .options(selectinload(Cicle.moduls).selectinload(Modul.ras))
    )
    cicle = (await session.execute(stmt)).scalar_one_or_none()
    if cicle is None:
        raise NotFound("cicle not found")
    return cicle


async def create_cicle(
    session: AsyncSession, payload: CicleCreate, *, actor_id: int, **meta: str | None
) -> Cicle:
    cicle = Cicle(
        codi=payload.codi.upper(),
        nom=payload.nom,
        familia_id=payload.familia_id,
        nivell=payload.nivell,
        durada=payload.durada,
        max_suspesos_recupera=payload.max_suspesos_recupera,
        pct_hores_no_promociona=payload.pct_hores_no_promociona,
    )
    session.add(cicle)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("cicle amb aquest codi ja existeix") from exc
    await audit.record(
        session, action="cicle_created", entity="cicle", entity_id=cicle.id, user_id=actor_id, **meta
    )
    return cicle


async def update_cicle(
    session: AsyncSession, cicle_id: int, payload: CicleUpdate, *, actor_id: int, **meta: str | None
) -> Cicle:
    cicle = await _get_or_404(session, Cicle, cicle_id)
    before = {
        "codi": cicle.codi,
        "nom": cicle.nom,
        "familia_id": cicle.familia_id,
        "nivell": cicle.nivell.value,
        "durada": cicle.durada,
    }
    data = _strip_unset(payload)
    if "codi" in data and data["codi"] is not None:
        data["codi"] = data["codi"].upper()
    for k, v in data.items():
        setattr(cicle, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks a uniqueness constraint") from exc
    await audit.record(
        session,
        action="cicle_updated",
        entity="cicle",
        entity_id=cicle.id,
        user_id=actor_id,
        before=before,
        after={**before, **data},
        **meta,
    )
    return cicle


async def soft_delete_cicle(
    session: AsyncSession, cicle_id: int, *, actor_id: int, **meta: str | None
) -> None:
    cicle = await _get_or_404(session, Cicle, cicle_id)
    cicle.deleted_at = datetime.now(timezone.utc)
    cicle.deleted_by_user_id = actor_id
    await audit.record(
        session, action="cicle_soft_deleted", entity="cicle", entity_id=cicle.id, user_id=actor_id, **meta
    )


# --- Mòduls -----------------------------------------------------------------

async def list_moduls(session: AsyncSession, *, cicle_id: int | None = None) -> list[Modul]:
    stmt = (
        select(Modul)
        .where(Modul.deleted_at.is_(None))
        .options(selectinload(Modul.ras))
    )
    if cicle_id is not None:
        stmt = stmt.where(Modul.cicle_id == cicle_id)
    stmt = stmt.order_by(Modul.curs, Modul.codi)
    return list((await session.execute(stmt)).scalars().unique().all())


async def create_modul(
    session: AsyncSession, payload: ModulCreate, *, actor_id: int, **meta: str | None
) -> Modul:
    await _get_or_404(session, Cicle, payload.cicle_id)
    modul = Modul(
        cicle_id=payload.cicle_id,
        codi=payload.codi.upper(),
        nom=payload.nom,
        curs=payload.curs,
        hores=payload.hores,
        bloquejant=payload.bloquejant,
    )
    session.add(modul)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("mòdul amb aquest codi ja existeix al cicle") from exc
    await audit.record(
        session, action="modul_created", entity="modul", entity_id=modul.id, user_id=actor_id, **meta
    )
    return await _get_modul_with_ras(session, modul.id)


async def update_modul(
    session: AsyncSession, modul_id: int, payload: ModulUpdate, *, actor_id: int, **meta: str | None
) -> Modul:
    modul = await _get_or_404(session, Modul, modul_id)
    before = {"codi": modul.codi, "nom": modul.nom, "curs": modul.curs, "hores": modul.hores}
    data = _strip_unset(payload)
    if "codi" in data and data["codi"] is not None:
        data["codi"] = data["codi"].upper()
    for k, v in data.items():
        setattr(modul, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks uniqueness") from exc
    await audit.record(
        session,
        action="modul_updated",
        entity="modul",
        entity_id=modul.id,
        user_id=actor_id,
        before=before,
        after={**before, **data},
        **meta,
    )
    return await _get_modul_with_ras(session, modul.id)


async def soft_delete_modul(
    session: AsyncSession, modul_id: int, *, actor_id: int, **meta: str | None
) -> None:
    modul = await _get_or_404(session, Modul, modul_id)
    modul.deleted_at = datetime.now(timezone.utc)
    modul.deleted_by_user_id = actor_id
    await audit.record(
        session, action="modul_soft_deleted", entity="modul", entity_id=modul.id, user_id=actor_id, **meta
    )


# --- RAs --------------------------------------------------------------------

async def list_ras(session: AsyncSession, *, modul_id: int) -> list[Ra]:
    stmt = (
        select(Ra)
        .where(Ra.modul_id == modul_id, Ra.deleted_at.is_(None))
        .order_by(Ra.ordre)
    )
    return list((await session.execute(stmt)).scalars().all())


async def create_ra(
    session: AsyncSession, payload: RaCreate, *, actor_id: int, **meta: str | None
) -> Ra:
    await _get_or_404(session, Modul, payload.modul_id)
    ra = Ra(
        modul_id=payload.modul_id,
        ordre=payload.ordre,
        codi=payload.codi.upper(),
        descripcio=payload.descripcio,
        pes=payload.pes,
    )
    session.add(ra)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("ja hi ha un RA amb aquest ordre al mòdul") from exc
    await audit.record(
        session, action="ra_created", entity="ra", entity_id=ra.id, user_id=actor_id, **meta
    )
    return ra


async def update_ra(
    session: AsyncSession, ra_id: int, payload: RaUpdate, *, actor_id: int, **meta: str | None
) -> Ra:
    ra = await _get_or_404(session, Ra, ra_id)
    before = {"ordre": ra.ordre, "codi": ra.codi, "descripcio": ra.descripcio, "pes": str(ra.pes)}
    data = _strip_unset(payload)
    if "codi" in data and data["codi"] is not None:
        data["codi"] = data["codi"].upper()
    for k, v in data.items():
        setattr(ra, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks uniqueness") from exc
    await audit.record(
        session,
        action="ra_updated",
        entity="ra",
        entity_id=ra.id,
        user_id=actor_id,
        before=before,
        after={**before, **{k: (str(v) if hasattr(v, "as_tuple") else v) for k, v in data.items()}},
        **meta,
    )
    return ra


async def soft_delete_ra(
    session: AsyncSession, ra_id: int, *, actor_id: int, **meta: str | None
) -> None:
    ra = await _get_or_404(session, Ra, ra_id)
    ra.deleted_at = datetime.now(timezone.utc)
    ra.deleted_by_user_id = actor_id
    await audit.record(
        session, action="ra_soft_deleted", entity="ra", entity_id=ra.id, user_id=actor_id, **meta
    )


# --- Cursos acadèmics -------------------------------------------------------

async def list_cursos(session: AsyncSession) -> list[CursAcademic]:
    stmt = select(CursAcademic).order_by(CursAcademic.nom.desc())
    return list((await session.execute(stmt)).scalars().all())


async def get_curs_actiu(session: AsyncSession) -> CursAcademic | None:
    stmt = select(CursAcademic).where(CursAcademic.actiu.is_(True)).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_curs(
    session: AsyncSession, payload: CursAcademicCreate, *, actor_id: int, **meta: str | None
) -> CursAcademic:
    curs = CursAcademic(**payload.model_dump())
    if curs.actiu:
        # Only one curs can be active at a time — deactivate others
        await _deactivate_other_cursos(session)
    session.add(curs)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("curs acadèmic ja existeix") from exc
    await audit.record(
        session, action="curs_created", entity="curs_academic", entity_id=curs.id, user_id=actor_id, **meta
    )
    return curs


async def update_curs(
    session: AsyncSession,
    curs_id: int,
    payload: CursAcademicUpdate,
    *,
    actor_id: int,
    **meta: str | None,
) -> CursAcademic:
    curs = await _get_or_404(session, CursAcademic, curs_id, soft=False)
    data = _strip_unset(payload)
    if data.get("actiu") is True:
        await _deactivate_other_cursos(session, except_id=curs_id)
    for k, v in data.items():
        setattr(curs, k, v)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("update breaks uniqueness") from exc
    await audit.record(
        session,
        action="curs_updated",
        entity="curs_academic",
        entity_id=curs.id,
        user_id=actor_id,
        after=data,
        **meta,
    )
    return curs


async def _deactivate_other_cursos(session: AsyncSession, *, except_id: int | None = None) -> None:
    stmt = select(CursAcademic).where(CursAcademic.actiu.is_(True))
    if except_id is not None:
        stmt = stmt.where(CursAcademic.id != except_id)
    for c in (await session.execute(stmt)).scalars().all():
        c.actiu = False
