"""Archive endpoints — the historical / search side of the system.

This is what makes "Arxiu" actually an archive:
  • alumne expedient — full academic history across all cursos acadèmics
  • grup expedient   — historical view of a grup classe (alumnes + tutor + notes)
  • cross-curs search — find an alumne or grup by partial match across years
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.api.v1.deps import CurrentUser, DbSession
from app.models.catalog import Cicle, CursAcademic, Modul, Ra
from app.models.grading import Avaluacio, QualificacioRa
from app.models.people import Alumne, GrupClasse, Matricula, TutorLegal

router = APIRouter(prefix="/archive", tags=["archive"])


# ============================================================================
# Alumne expedient (history)
# ============================================================================

class _AlumneSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dni: str | None
    ralc: str
    nom: str
    cognoms: str
    email: str | None
    telefon: str | None
    data_naixement: date | None


class _TutorLegalRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nom: str
    email: str | None
    telefon: str | None


class _AvaluacioNotaRow(BaseModel):
    avaluacio_id: int
    avaluacio_nom: str
    avaluacio_estat: str
    avaluacio_ordre: int
    notes: dict[str, float | None]  # codi RA → nota
    mitjana_modul: float | None     # mean of available RA notes


class _ModulRow(BaseModel):
    modul_id: int
    modul_codi: str
    modul_nom: str
    curs: int
    ras: list[dict]                  # [{id, codi, ordre, descripcio, pes}]
    avaluacions: list[_AvaluacioNotaRow]


class _MatriculaRow(BaseModel):
    matricula_id: int
    curs_acad_id: int
    curs_acad_nom: str
    cicle_id: int
    cicle_codi: str
    cicle_nom: str
    curs: int
    grup_id: int
    grup_codi: str
    tipus: str
    estat: str
    created_at: datetime
    moduls: list[_ModulRow]


class AlumneExpedientResponse(BaseModel):
    alumne: _AlumneSummary
    tutors_legals: list[_TutorLegalRow]
    matricules: list[_MatriculaRow]   # ordered by curs_acad desc (most recent first)


@router.get("/alumne/{alumne_id}/expedient", response_model=AlumneExpedientResponse)
async def alumne_expedient(
    alumne_id: int,
    db: DbSession,
    _: CurrentUser,
):
    """Full academic history of an alumne across all cursos acadèmics."""
    alumne = await db.get(Alumne, alumne_id)
    if alumne is None or alumne.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alumne_not_found")

    # Tutors legals
    tutors = list(
        (
            await db.execute(
                select(TutorLegal).where(TutorLegal.alumne_id == alumne.id)
            )
        )
        .scalars()
        .all()
    )

    # All matricules for this alumne, joined with the curs + cicle + grup
    matr_stmt = (
        select(Matricula)
        .where(Matricula.alumne_id == alumne.id, Matricula.deleted_at.is_(None))
        .order_by(Matricula.curs_acad_id.desc(), Matricula.created_at.desc())
    )
    matricules = list((await db.execute(matr_stmt)).scalars().all())

    rows: list[_MatriculaRow] = []
    for m in matricules:
        curs = await db.get(CursAcademic, m.curs_acad_id)
        cicle = await db.get(Cicle, m.cicle_id)
        grup = await db.get(GrupClasse, m.grup_id)
        if curs is None or cicle is None or grup is None:
            continue

        # Mòduls of this matricula's cicle for the matriculated curs
        moduls = list(
            (
                await db.execute(
                    select(Modul)
                    .where(
                        Modul.cicle_id == cicle.id,
                        Modul.curs == m.curs,
                        Modul.deleted_at.is_(None),
                    )
                    .options(selectinload(Modul.ras))
                    .order_by(Modul.codi)
                )
            )
            .scalars()
            .unique()
            .all()
        )

        # Avaluacions of this curs
        avals = list(
            (
                await db.execute(
                    select(Avaluacio)
                    .where(
                        Avaluacio.curs_acad_id == curs.id,
                        Avaluacio.deleted_at.is_(None),
                    )
                    .order_by(Avaluacio.ordre)
                )
            )
            .scalars()
            .all()
        )

        # Qualificacions RA for this matricula
        qras = list(
            (
                await db.execute(
                    select(QualificacioRa).where(
                        QualificacioRa.matricula_id == m.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        # Index by (avaluacio_id, ra_id) → nota
        by_aval_ra: dict[tuple[int, int], Decimal | None] = {
            (q.avaluacio_id, q.ra_id): q.nota for q in qras
        }

        modul_rows: list[_ModulRow] = []
        for mod in moduls:
            ras_sorted = sorted(mod.ras, key=lambda r: r.ordre)
            ras_payload = [
                {
                    "id": r.id,
                    "codi": r.codi,
                    "ordre": r.ordre,
                    "descripcio": r.descripcio,
                    "pes": float(r.pes) if r.pes is not None else 0.0,
                }
                for r in ras_sorted
            ]

            aval_rows: list[_AvaluacioNotaRow] = []
            for aval in avals:
                ra_notes: dict[str, float | None] = {}
                valid: list[float] = []
                for r in ras_sorted:
                    n = by_aval_ra.get((aval.id, r.id))
                    if n is None:
                        ra_notes[r.codi] = None
                    else:
                        f = float(n)
                        ra_notes[r.codi] = f
                        valid.append(f)
                mean = round(sum(valid) / len(valid), 2) if valid else None
                aval_rows.append(
                    _AvaluacioNotaRow(
                        avaluacio_id=aval.id,
                        avaluacio_nom=aval.nom,
                        avaluacio_estat=aval.estat.value if hasattr(aval.estat, "value") else str(aval.estat),
                        avaluacio_ordre=aval.ordre,
                        notes=ra_notes,
                        mitjana_modul=mean,
                    )
                )

            modul_rows.append(
                _ModulRow(
                    modul_id=mod.id,
                    modul_codi=mod.codi,
                    modul_nom=mod.nom,
                    curs=mod.curs,
                    ras=ras_payload,
                    avaluacions=aval_rows,
                )
            )

        rows.append(
            _MatriculaRow(
                matricula_id=m.id,
                curs_acad_id=curs.id,
                curs_acad_nom=curs.nom,
                cicle_id=cicle.id,
                cicle_codi=cicle.codi,
                cicle_nom=cicle.nom,
                curs=m.curs,
                grup_id=grup.id,
                grup_codi=grup.codi,
                tipus=m.tipus.value if hasattr(m.tipus, "value") else str(m.tipus),
                estat=m.estat.value if hasattr(m.estat, "value") else str(m.estat),
                created_at=m.created_at,
                moduls=modul_rows,
            )
        )

    return AlumneExpedientResponse(
        alumne=_AlumneSummary.model_validate(alumne),
        tutors_legals=[_TutorLegalRow.model_validate(t) for t in tutors],
        matricules=rows,
    )


# ============================================================================
# Grup expedient — historical class view
# ============================================================================

class _GrupExpedientAlumne(BaseModel):
    alumne_id: int
    matricula_id: int
    nom: str
    cognoms: str
    dni: str | None
    ralc: str
    estat: str


class GrupExpedientResponse(BaseModel):
    grup_id: int
    grup_codi: str
    curs_acad_id: int
    curs_acad_nom: str
    cicle_codi: str
    cicle_nom: str
    cicle_nivell: str
    curs: int
    tutor_user_id: int | None
    tutor_nom_complet: str | None
    alumnes: list[_GrupExpedientAlumne]


@router.get("/grup/{grup_id}/expedient", response_model=GrupExpedientResponse)
async def grup_expedient(grup_id: int, db: DbSession, _: CurrentUser):
    grup = await db.get(GrupClasse, grup_id)
    if grup is None or grup.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "grup_not_found")

    curs = await db.get(CursAcademic, grup.curs_acad_id)
    cicle = await db.get(Cicle, grup.cicle_id)
    tutor = grup.tutor

    matr_stmt = (
        select(Matricula, Alumne)
        .join(Alumne, Alumne.id == Matricula.alumne_id)
        .where(Matricula.grup_id == grup.id, Matricula.deleted_at.is_(None))
        .order_by(Alumne.cognoms, Alumne.nom)
    )
    matr_rows = list((await db.execute(matr_stmt)).all())

    return GrupExpedientResponse(
        grup_id=grup.id,
        grup_codi=grup.codi,
        curs_acad_id=curs.id if curs else 0,
        curs_acad_nom=curs.nom if curs else "",
        cicle_codi=cicle.codi if cicle else "",
        cicle_nom=cicle.nom if cicle else "",
        cicle_nivell=(cicle.nivell.value if cicle and hasattr(cicle.nivell, "value") else str(cicle.nivell) if cicle else ""),
        curs=grup.curs,
        tutor_user_id=grup.tutor_user_id,
        tutor_nom_complet=(f"{tutor.nom} {tutor.cognoms}" if tutor else None),
        alumnes=[
            _GrupExpedientAlumne(
                alumne_id=a.id,
                matricula_id=m.id,
                nom=a.nom,
                cognoms=a.cognoms,
                dni=a.dni,
                ralc=a.ralc,
                estat=m.estat.value if hasattr(m.estat, "value") else str(m.estat),
            )
            for (m, a) in matr_rows
        ],
    )


# ============================================================================
# Cross-archive search (used by the Arxiu page tree + CmdK alternative)
# ============================================================================

class _SearchHit(BaseModel):
    kind: str
    id: int
    label: str
    sub: str | None = None
    extra: dict = {}


@router.get("/search", response_model=list[_SearchHit])
async def archive_search(
    db: DbSession,
    _: CurrentUser,
    q: str = Query(..., min_length=2, max_length=120),
):
    """Global search across the archive: alumnes (DNI/RALC/nom/cognoms),
    grups (codi), cicles (codi/nom). Returns top ~30 hits across all kinds."""
    pattern = f"%{q.strip().lower()}%"
    hits: list[_SearchHit] = []

    # Alumnes
    alumnes = list(
        (
            await db.execute(
                select(Alumne)
                .where(
                    Alumne.deleted_at.is_(None),
                    or_(
                        func.lower(Alumne.nom).like(pattern),
                        func.lower(Alumne.cognoms).like(pattern),
                        Alumne.dni.ilike(pattern),
                        Alumne.ralc.ilike(pattern),
                        Alumne.email.ilike(pattern),
                    ),
                )
                .order_by(Alumne.cognoms, Alumne.nom)
                .limit(12)
            )
        )
        .scalars()
        .all()
    )
    for a in alumnes:
        hits.append(
            _SearchHit(
                kind="alumne",
                id=a.id,
                label=f"{a.cognoms}, {a.nom}",
                sub=f"DNI {a.dni or '—'} · RALC {a.ralc}",
                extra={"alumne_id": a.id},
            )
        )

    # Grups — also try to match by "{cicle} {curs} {any}" patterns
    grup_stmt = (
        select(GrupClasse, Cicle, CursAcademic)
        .join(Cicle, Cicle.id == GrupClasse.cicle_id)
        .join(CursAcademic, CursAcademic.id == GrupClasse.curs_acad_id)
        .where(
            GrupClasse.deleted_at.is_(None),
            or_(
                func.lower(GrupClasse.codi).like(pattern),
                func.lower(Cicle.codi).like(pattern),
                func.lower(Cicle.nom).like(pattern),
                func.lower(CursAcademic.nom).like(pattern),
            ),
        )
        .order_by(CursAcademic.nom.desc(), GrupClasse.codi)
        .limit(12)
    )
    grup_rows = list((await db.execute(grup_stmt)).all())
    for grup, cicle, curs in grup_rows:
        hits.append(
            _SearchHit(
                kind="grup",
                id=grup.id,
                label=f"{grup.codi} · {curs.nom}",
                sub=f"{cicle.codi} · {cicle.nom}",
                extra={"grup_id": grup.id, "curs_acad_id": curs.id},
            )
        )

    # Cicles
    cicles = list(
        (
            await db.execute(
                select(Cicle)
                .where(
                    Cicle.deleted_at.is_(None),
                    or_(
                        func.lower(Cicle.codi).like(pattern),
                        func.lower(Cicle.nom).like(pattern),
                    ),
                )
                .limit(8)
            )
        )
        .scalars()
        .all()
    )
    for c in cicles:
        hits.append(
            _SearchHit(
                kind="cicle",
                id=c.id,
                label=f"{c.codi} · {c.nom}",
                sub=(c.nivell.value if hasattr(c.nivell, "value") else str(c.nivell)),
                extra={"cicle_id": c.id},
            )
        )

    return hits[:30]
