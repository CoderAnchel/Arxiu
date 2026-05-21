"""Qualificacions service — read for the grade spreadsheet, batch upsert with
permission enforcement on every row.

The bulk PATCH endpoint receives a list of {matricula_id, ra_id, nota, comentari}
items. For each item the service:
  1. Looks up the matrícula (and its grup) — verifies it exists.
  2. Looks up the RA's mòdul (to match assignacions).
  3. Loads the avaluació and the actor's relationship (assignment row +
     tutorship of grup).
  4. Calls the pure permission predicate.
  5. Either upserts the qualificació or marks the row as denied.

Returns a per-row result so the frontend can highlight failures without
aborting the whole save.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import permissions
from app.core.exceptions import NotFound
from app.models.catalog import Modul, Ra
from app.models.grading import Avaluacio, QualificacioModul, QualificacioRa
from app.models.people import AssignacioDocent, GrupClasse, Matricula
from app.models.user import User
from app.services import audit


# ---------------------------------------------------------------------------
# Read — grade spreadsheet
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class GradeMatrixCell:
    matricula_id: int
    ra_id: int
    nota: float | None
    comentari: str | None


@dataclass(frozen=True, slots=True)
class GradeMatrixModulCell:
    matricula_id: int
    nota: float | None
    comentari: str | None


@dataclass(frozen=True, slots=True)
class GradeMatrixAlumne:
    matricula_id: int
    alumne_id: int
    nom: str
    cognoms: str
    dni: str | None
    ralc: str


async def load_grade_matrix(
    session: AsyncSession,
    *,
    grup_id: int,
    modul_id: int,
    avaluacio_id: int,
) -> tuple[
    list[GradeMatrixAlumne],
    list[Ra],
    list[GradeMatrixCell],
    list[GradeMatrixModulCell],
]:
    # Only matrícules whose curs matches the mòdul's curs: a 1r-curs student
    # can't be graded against a 2n-curs module of the same cicle.
    modul = await session.get(Modul, modul_id)
    matr_stmt = (
        select(Matricula)
        .where(Matricula.grup_id == grup_id, Matricula.deleted_at.is_(None))
    )
    if modul is not None:
        matr_stmt = matr_stmt.where(Matricula.curs == modul.curs)
    matricules = list((await session.execute(matr_stmt)).scalars().all())

    alumnes = [
        GradeMatrixAlumne(
            matricula_id=m.id,
            alumne_id=m.alumne.id,
            nom=m.alumne.nom,
            cognoms=m.alumne.cognoms,
            dni=m.alumne.dni,
            ralc=m.alumne.ralc,
        )
        for m in matricules
    ]
    alumnes.sort(key=lambda a: (a.cognoms, a.nom))

    # RAs of the mòdul
    ras = list(
        (
            await session.execute(
                select(Ra).where(Ra.modul_id == modul_id, Ra.deleted_at.is_(None)).order_by(Ra.ordre)
            )
        )
        .scalars()
        .all()
    )

    matricula_ids = [a.matricula_id for a in alumnes]
    ra_ids = [r.id for r in ras]
    if not matricula_ids:
        return alumnes, ras, [], []

    cells: list[GradeMatrixCell] = []
    if ra_ids:
        cells_stmt = select(QualificacioRa).where(
            QualificacioRa.avaluacio_id == avaluacio_id,
            QualificacioRa.matricula_id.in_(matricula_ids),
            QualificacioRa.ra_id.in_(ra_ids),
        )
        qras = list((await session.execute(cells_stmt)).scalars().all())
        cells = [
            GradeMatrixCell(
                matricula_id=q.matricula_id,
                ra_id=q.ra_id,
                nota=float(q.nota) if q.nota is not None else None,
                comentari=q.comentari,
            )
            for q in qras
        ]

    # Manual modul-level overrides for this (modul, avaluacio).
    modul_cells_stmt = select(QualificacioModul).where(
        QualificacioModul.avaluacio_id == avaluacio_id,
        QualificacioModul.modul_id == modul_id,
        QualificacioModul.matricula_id.in_(matricula_ids),
    )
    qmods = list((await session.execute(modul_cells_stmt)).scalars().all())
    modul_cells = [
        GradeMatrixModulCell(
            matricula_id=q.matricula_id,
            nota=float(q.nota) if q.nota is not None else None,
            comentari=q.comentari,
        )
        for q in qmods
    ]
    return alumnes, ras, cells, modul_cells


# ---------------------------------------------------------------------------
# Permission helpers (DB-aware wrappers around pure predicates)
# ---------------------------------------------------------------------------

async def _has_assignacio(
    session: AsyncSession, *, user_id: int, grup_id: int, modul_id: int, curs_acad_id: int
) -> bool:
    stmt = select(
        exists().where(
            and_(
                AssignacioDocent.user_id == user_id,
                AssignacioDocent.grup_id == grup_id,
                AssignacioDocent.modul_id == modul_id,
                AssignacioDocent.curs_acad_id == curs_acad_id,
                AssignacioDocent.deleted_at.is_(None),
            )
        )
    )
    return bool((await session.execute(stmt)).scalar())


async def _is_tutor_of_grup(session: AsyncSession, *, user_id: int, grup_id: int) -> bool:
    stmt = select(GrupClasse.tutor_user_id).where(GrupClasse.id == grup_id)
    tutor_id = (await session.execute(stmt)).scalar_one_or_none()
    return tutor_id == user_id


# ---------------------------------------------------------------------------
# Bulk upsert
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class QualifPatch:
    matricula_id: int
    ra_id: int
    nota: Decimal | None
    comentari: str | None


@dataclass(frozen=True, slots=True)
class QualifPatchResult:
    matricula_id: int
    ra_id: int
    ok: bool
    error: str | None = None


async def batch_upsert_ra(
    session: AsyncSession,
    *,
    avaluacio_id: int,
    patches: Iterable[QualifPatch],
    actor: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> list[QualifPatchResult]:
    avaluacio = await session.get(Avaluacio, avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise NotFound("avaluacio not found")

    results: list[QualifPatchResult] = []

    # Pre-cache per (grup, modul) the assignacio + tutorship flags to avoid N queries
    perm_cache: dict[tuple[int, int], tuple[bool, bool]] = {}

    for p in patches:
        matr = await session.get(Matricula, p.matricula_id)
        if matr is None or matr.deleted_at is not None:
            results.append(QualifPatchResult(p.matricula_id, p.ra_id, False, "matricula_not_found"))
            continue

        ra = await session.get(Ra, p.ra_id)
        if ra is None or ra.deleted_at is not None:
            results.append(QualifPatchResult(p.matricula_id, p.ra_id, False, "ra_not_found"))
            continue

        modul = await session.get(Modul, ra.modul_id)
        if modul is None:
            results.append(QualifPatchResult(p.matricula_id, p.ra_id, False, "modul_not_found"))
            continue

        if matr.curs != modul.curs:
            results.append(
                QualifPatchResult(p.matricula_id, p.ra_id, False, "curs_mismatch")
            )
            continue

        cache_key = (matr.grup_id, modul.id)
        if cache_key in perm_cache:
            has_assig, is_tutor = perm_cache[cache_key]
        else:
            has_assig = await _has_assignacio(
                session,
                user_id=actor.id,
                grup_id=matr.grup_id,
                modul_id=modul.id,
                curs_acad_id=avaluacio.curs_acad_id,
            )
            is_tutor = await _is_tutor_of_grup(session, user_id=actor.id, grup_id=matr.grup_id)
            perm_cache[cache_key] = (has_assig, is_tutor)

        if not permissions.can_edit_qualif_ra(
            user=actor,
            avaluacio_estat=avaluacio.estat.value,
            has_assignacio=has_assig,
            is_tutor_of_grup=is_tutor,
        ):
            results.append(QualifPatchResult(p.matricula_id, p.ra_id, False, "permission_denied"))
            continue

        if p.nota is not None and (p.nota < 0 or p.nota > 10):
            results.append(QualifPatchResult(p.matricula_id, p.ra_id, False, "nota_out_of_range"))
            continue

        # Upsert (find existing, else create)
        existing_stmt = select(QualificacioRa).where(
            QualificacioRa.matricula_id == p.matricula_id,
            QualificacioRa.ra_id == p.ra_id,
            QualificacioRa.avaluacio_id == avaluacio_id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing is None:
            row = QualificacioRa(
                matricula_id=p.matricula_id,
                ra_id=p.ra_id,
                avaluacio_id=avaluacio_id,
                nota=p.nota,
                comentari=p.comentari,
                professor_user_id=actor.id,
            )
            session.add(row)
            await session.flush()
            await audit.record(
                session,
                action="qualif_ra_created",
                entity="qualif_ra",
                entity_id=row.id,
                user_id=actor.id,
                after={"nota": str(p.nota) if p.nota is not None else None,
                       "matricula_id": p.matricula_id, "ra_id": p.ra_id},
                ip=ip,
                user_agent=user_agent,
            )
        else:
            before = {
                "nota": str(existing.nota) if existing.nota is not None else None,
                "comentari": existing.comentari,
            }
            existing.nota = p.nota
            existing.comentari = p.comentari
            existing.professor_user_id = actor.id
            existing.updated_at = datetime.now(timezone.utc)
            await audit.record(
                session,
                action="qualif_ra_updated",
                entity="qualif_ra",
                entity_id=existing.id,
                user_id=actor.id,
                before=before,
                after={"nota": str(p.nota) if p.nota is not None else None,
                       "comentari": p.comentari},
                ip=ip,
                user_agent=user_agent,
            )

        results.append(QualifPatchResult(p.matricula_id, p.ra_id, True))

    return results


# ---------------------------------------------------------------------------
# Mòdul-level manual override (the final note that bypasses the RA mean)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class QualifModulPatch:
    matricula_id: int
    nota: Decimal | None
    comentari: str | None


@dataclass(frozen=True, slots=True)
class QualifModulPatchResult:
    matricula_id: int
    ok: bool
    error: str | None = None


async def batch_upsert_modul(
    session: AsyncSession,
    *,
    avaluacio_id: int,
    modul_id: int,
    patches: Iterable[QualifModulPatch],
    actor: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> list[QualifModulPatchResult]:
    avaluacio = await session.get(Avaluacio, avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise NotFound("avaluacio not found")
    modul = await session.get(Modul, modul_id)
    if modul is None or modul.deleted_at is not None:
        raise NotFound("modul not found")

    results: list[QualifModulPatchResult] = []
    perm_cache: dict[int, tuple[bool, bool]] = {}  # grup_id -> (has_assig, is_tutor)

    for p in patches:
        matr = await session.get(Matricula, p.matricula_id)
        if matr is None or matr.deleted_at is not None:
            results.append(QualifModulPatchResult(p.matricula_id, False, "matricula_not_found"))
            continue

        if matr.curs != modul.curs:
            results.append(QualifModulPatchResult(p.matricula_id, False, "curs_mismatch"))
            continue

        if matr.grup_id in perm_cache:
            has_assig, is_tutor = perm_cache[matr.grup_id]
        else:
            has_assig = await _has_assignacio(
                session,
                user_id=actor.id,
                grup_id=matr.grup_id,
                modul_id=modul.id,
                curs_acad_id=avaluacio.curs_acad_id,
            )
            is_tutor = await _is_tutor_of_grup(session, user_id=actor.id, grup_id=matr.grup_id)
            perm_cache[matr.grup_id] = (has_assig, is_tutor)

        if not permissions.can_edit_qualif_modul(
            user=actor,
            avaluacio_estat=avaluacio.estat.value,
            has_assignacio=has_assig,
            is_tutor_of_grup=is_tutor,
        ):
            results.append(QualifModulPatchResult(p.matricula_id, False, "permission_denied"))
            continue

        if p.nota is not None and (p.nota < 0 or p.nota > 10):
            results.append(QualifModulPatchResult(p.matricula_id, False, "nota_out_of_range"))
            continue

        existing_stmt = select(QualificacioModul).where(
            QualificacioModul.matricula_id == p.matricula_id,
            QualificacioModul.modul_id == modul_id,
            QualificacioModul.avaluacio_id == avaluacio_id,
        )
        existing = (await session.execute(existing_stmt)).scalar_one_or_none()

        if existing is None:
            row = QualificacioModul(
                matricula_id=p.matricula_id,
                modul_id=modul_id,
                avaluacio_id=avaluacio_id,
                nota=p.nota,
                comentari=p.comentari,
                professor_user_id=actor.id,
            )
            session.add(row)
            await session.flush()
            await audit.record(
                session,
                action="qualif_modul_created",
                entity="qualif_modul",
                entity_id=row.id,
                user_id=actor.id,
                after={
                    "nota": str(p.nota) if p.nota is not None else None,
                    "matricula_id": p.matricula_id,
                    "modul_id": modul_id,
                },
                ip=ip,
                user_agent=user_agent,
            )
        else:
            before = {
                "nota": str(existing.nota) if existing.nota is not None else None,
                "comentari": existing.comentari,
            }
            existing.nota = p.nota
            existing.comentari = p.comentari
            existing.professor_user_id = actor.id
            await audit.record(
                session,
                action="qualif_modul_updated",
                entity="qualif_modul",
                entity_id=existing.id,
                user_id=actor.id,
                before=before,
                after={
                    "nota": str(p.nota) if p.nota is not None else None,
                    "comentari": p.comentari,
                },
                ip=ip,
                user_agent=user_agent,
            )

        results.append(QualifModulPatchResult(p.matricula_id, True))

    return results
