"""Butlleti renderer — assembles the data for one alumne + avaluació and produces a PDF.

Data flow:
  alumne + avaluació → matrícula (via curs_acad_id) → grup → cicle → mòduls of cicle
                     → for each mòdul: RAs → qualificacions_ra in this avaluació
                     → render Jinja2 template → WeasyPrint → PDF bytes
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from statistics import mean
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.catalog import Cicle, Modul, Ra
from app.models.grading import Avaluacio, QualificacioRa
from app.models.people import Alumne, GrupClasse, Matricula

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True, slots=True)
class ButlletiOpts:
    detall_ra: bool = True
    comentaris: bool = True
    distribucio_grup: bool = False
    signatura: bool = True
    logo_centre: bool = True


@dataclass(frozen=True, slots=True)
class _RaNote:
    ra: Ra
    nota: Decimal | None


@dataclass(frozen=True, slots=True)
class _ModulRow:
    modul: Modul
    ra_notes: list[_RaNote]
    nota: float | None    # arithmetic mean of available RA notes, used as the mòdul nota


async def _gather_butlleti_data(
    session: AsyncSession, *, alumne_id: int, avaluacio_id: int
) -> dict[str, Any]:
    alumne = await session.get(Alumne, alumne_id)
    if alumne is None or alumne.deleted_at is not None:
        raise NotFound("alumne not found")

    avaluacio = await session.get(Avaluacio, avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise NotFound("avaluacio not found")

    matr_stmt = (
        select(Matricula)
        .where(
            Matricula.alumne_id == alumne_id,
            Matricula.curs_acad_id == avaluacio.curs_acad_id,
            Matricula.deleted_at.is_(None),
        )
        .limit(1)
    )
    matricula = (await session.execute(matr_stmt)).scalar_one_or_none()
    if matricula is None:
        raise NotFound("alumne has no active matrícula in this curs acadèmic")

    grup = await session.get(GrupClasse, matricula.grup_id)
    cicle = await session.get(Cicle, matricula.cicle_id)
    if grup is None or cicle is None:
        raise NotFound("grup or cicle missing")

    moduls_stmt = (
        select(Modul)
        .where(
            Modul.cicle_id == cicle.id,
            Modul.curs == matricula.curs,
            Modul.deleted_at.is_(None),
        )
        .order_by(Modul.codi)
    )
    moduls = list((await session.execute(moduls_stmt)).scalars().all())

    rows: list[_ModulRow] = []
    aprovats = 0
    finals: list[float] = []

    for m in moduls:
        ras_stmt = (
            select(Ra)
            .where(Ra.modul_id == m.id, Ra.deleted_at.is_(None))
            .order_by(Ra.ordre)
        )
        ras = list((await session.execute(ras_stmt)).scalars().all())

        ra_notes: list[_RaNote] = []
        for ra in ras:
            q_stmt = (
                select(QualificacioRa)
                .where(
                    QualificacioRa.matricula_id == matricula.id,
                    QualificacioRa.ra_id == ra.id,
                    QualificacioRa.avaluacio_id == avaluacio.id,
                )
                .limit(1)
            )
            q = (await session.execute(q_stmt)).scalar_one_or_none()
            ra_notes.append(_RaNote(ra=ra, nota=q.nota if q else None))

        valid = [float(n.nota) for n in ra_notes if n.nota is not None]
        nota_mod = round(mean(valid), 1) if valid else None
        if nota_mod is not None:
            finals.append(nota_mod)
            if nota_mod >= 5:
                aprovats += 1

        rows.append(_ModulRow(modul=m, ra_notes=ra_notes, nota=nota_mod))

    mitjana = round(mean(finals), 2) if finals else None

    return {
        "alumne": alumne,
        "avaluacio": avaluacio,
        "matricula": matricula,
        "grup": grup,
        "cicle": cicle,
        "moduls": rows,
        "aprovats": aprovats,
        "total_moduls": len(moduls),
        "mitjana": mitjana,
        "curs_acad_nom": avaluacio.curs_acad.nom if avaluacio.curs_acad else "",
        "comentari_global": (
            "L'alumne/a mostra una progressió positiva durant aquesta avaluació. "
            "Cal continuar amb la mateixa dedicació de cara a la propera."
            if mitjana and mitjana >= 5
            else "Cal reforçar la dedicació al treball de classe i als lliuraments puntuals."
            if mitjana is not None
            else None
        ),
    }


async def render_butlleti_html(
    session: AsyncSession,
    *,
    alumne_id: int,
    avaluacio_id: int,
    opts: ButlletiOpts | None = None,
) -> str:
    data = await _gather_butlleti_data(session, alumne_id=alumne_id, avaluacio_id=avaluacio_id)
    template = _jinja.get_template("pdf/butlleti.html")
    return template.render(**data, opts=opts or ButlletiOpts())


async def render_butlleti_pdf(
    session: AsyncSession,
    *,
    alumne_id: int,
    avaluacio_id: int,
    opts: ButlletiOpts | None = None,
) -> bytes:
    """Render the butlleti as a PDF byte string. Raises NotFound on missing data."""
    html = await render_butlleti_html(
        session, alumne_id=alumne_id, avaluacio_id=avaluacio_id, opts=opts
    )

    # Lazy-import WeasyPrint — its system deps are present only in the backend container.
    # In tests we monkeypatch render_butlleti_pdf directly to avoid the import.
    from weasyprint import HTML

    return HTML(string=html).write_pdf()


def render_butlleti_email(
    *,
    assumpte: str,
    alumne_nom_complet: str,
    grup_codi: str,
    avaluacio_nom: str,
    curs_acad_nom: str,
) -> str:
    template = _jinja.get_template("email/butlleti.html")
    return template.render(
        assumpte=assumpte,
        alumne_nom_complet=alumne_nom_complet,
        grup_codi=grup_codi,
        avaluacio_nom=avaluacio_nom,
        curs_acad_nom=curs_acad_nom,
    )
