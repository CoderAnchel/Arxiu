"""Acta de Junta d'Avaluació — official PDF document of the deliberation.

The acta is the LEGAL document produced after a junta d'avaluació:
- Header: centre, grup, curs, avaluació, data
- Body: each alumne with their final nota per mòdul + a derived decision
  (Apte / Recupera / No promociona)
- Footer: signatures (tutor + cap d'estudis)

Decisions are derived heuristically from notes:
- Apte (≥ 5 a tots els mòduls)
- Recupera (1 o 2 suspesos, pot recuperar)
- No promociona (3+ suspesos)
- Pendent (algun mòdul sense qualificar)

The tutor pot afegir un comentari lliure que es desa al `comentari` del
`QualificacioModul` corresponent — així apareix a l'acta.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.models.catalog import Cicle, CursAcademic, Modul, Ra
from app.models.grading import Avaluacio, QualificacioModul, QualificacioRa
from app.models.people import Alumne, GrupClasse, Matricula
from app.models.user import User

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


@dataclass(frozen=True, slots=True)
class ActaRaNota:
    codi: str
    descripcio: str
    pes: float
    nota: float | None


@dataclass(frozen=True, slots=True)
class ActaModulNota:
    codi: str
    nom: str
    nota: float | None
    is_manual: bool
    comentari: str | None
    ras: list[ActaRaNota]  # detail of the individual RAs that feed the final
    hores: int = 0
    bloquejant: bool = False


@dataclass(frozen=True, slots=True)
class ActaAlumneRow:
    cognoms: str
    nom: str
    dni: str | None
    ralc: str
    notes_per_modul: list[ActaModulNota]
    decisio: str          # "Apte" | "Recupera" | "No promociona" | "Pendent"
    suspesos: int
    no_qualificats: int
    motiu_decisio: str = ""  # explicació humana del per què


def _derive_decisio(
    notes: list[ActaModulNota],
    *,
    max_suspesos_recupera: int = 2,
    pct_hores_no_promociona: float | None = None,
) -> tuple[str, int, int, str]:
    """Returns (decisio, n_suspesos, n_pendents, motiu).

    Rule order (highest priority first):
      1. Si manca alguna nota → "Pendent" (cal informar abans d'avaluar)
      2. Si suspèn un mòdul bloquejant (FCT/Projecte/…) → "No promociona"
      3. Si el % d'hores suspeses supera el llindar del cicle → "No promociona"
      4. Si suspesos == 0 → "Apte"
      5. Si suspesos <= max_suspesos_recupera del cicle → "Recupera"
      6. Altrament → "No promociona"
    """
    suspesos = 0
    pendents = 0
    bloquejant_suspes: str | None = None
    hores_total = 0
    hores_suspeses = 0

    for n in notes:
        hores_total += n.hores
        if n.nota is None:
            pendents += 1
            continue
        if n.nota < 5:
            suspesos += 1
            hores_suspeses += n.hores
            if n.bloquejant and bloquejant_suspes is None:
                bloquejant_suspes = n.codi

    if pendents > 0:
        return ("Pendent", suspesos, pendents, f"{pendents} mòdul/s sense nota")

    if bloquejant_suspes is not None:
        return (
            "No promociona",
            suspesos,
            0,
            f"Mòdul bloquejant {bloquejant_suspes} suspès",
        )

    if pct_hores_no_promociona is not None and hores_total > 0:
        pct = 100 * hores_suspeses / hores_total
        if pct > float(pct_hores_no_promociona):
            return (
                "No promociona",
                suspesos,
                0,
                f"{pct:.1f}% d'hores suspeses (llindar {pct_hores_no_promociona}%)",
            )

    if suspesos == 0:
        return ("Apte", 0, 0, "Tots els mòduls aprovats")
    if suspesos <= max_suspesos_recupera:
        return (
            "Recupera",
            suspesos,
            0,
            f"{suspesos} mòdul/s suspesos (límit del cicle: {max_suspesos_recupera})",
        )
    return (
        "No promociona",
        suspesos,
        0,
        f"{suspesos} mòduls suspesos supera el límit del cicle ({max_suspesos_recupera})",
    )


async def _load_ras_with_notes(
    session: AsyncSession,
    *,
    matricula_id: int,
    modul: Modul,
    avaluacio_id: int,
) -> tuple[list[ActaRaNota], float | None]:
    """Returns the per-RA notes list AND the weighted mean (if all RAs scored).

    The list always contains every RA of the mòdul (even when not yet
    qualified), so the acta detail can show "—" for missing values.
    """
    ras = list(
        (
            await session.execute(
                select(Ra)
                .where(Ra.modul_id == modul.id, Ra.deleted_at.is_(None))
                .order_by(Ra.ordre)
            )
        )
        .scalars()
        .all()
    )
    if not ras:
        return [], None
    qras = list(
        (
            await session.execute(
                select(QualificacioRa).where(
                    QualificacioRa.matricula_id == matricula_id,
                    QualificacioRa.avaluacio_id == avaluacio_id,
                    QualificacioRa.ra_id.in_([r.id for r in ras]),
                )
            )
        )
        .scalars()
        .all()
    )
    by_ra: dict[int, Decimal] = {q.ra_id: q.nota for q in qras if q.nota is not None}

    detail: list[ActaRaNota] = [
        ActaRaNota(
            codi=r.codi,
            descripcio=r.descripcio,
            pes=float(r.pes) if r.pes is not None else 0.0,
            nota=float(by_ra[r.id]) if r.id in by_ra else None,
        )
        for r in ras
    ]
    if len(by_ra) < len(ras):
        return detail, None  # mitjana només significativa quan totes les RA tenen nota
    total_w = sum(float(r.pes) for r in ras if r.pes is not None) or 1.0
    weighted = sum(float(by_ra[r.id]) * float(r.pes or 0) for r in ras)
    return detail, round(weighted / total_w, 2)


async def render_acta_html(
    session: AsyncSession,
    *,
    grup_id: int,
    avaluacio_id: int,
    tutor_signat: str | None = None,
    cap_estudis_signat: str | None = None,
    director_signat: str | None = None,
) -> str:
    grup = await session.get(GrupClasse, grup_id)
    aval = await session.get(Avaluacio, avaluacio_id)
    if grup is None or aval is None:
        raise NotFound("grup or avaluacio not found")
    curs = await session.get(CursAcademic, grup.curs_acad_id)
    cicle = await session.get(Cicle, grup.cicle_id)
    tutor = await session.get(User, grup.tutor_user_id) if grup.tutor_user_id else None

    moduls = list(
        (
            await session.execute(
                select(Modul)
                .where(
                    Modul.cicle_id == grup.cicle_id,
                    Modul.curs == grup.curs,
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

    matricules = list(
        (
            await session.execute(
                select(Matricula)
                .where(
                    Matricula.grup_id == grup_id,
                    Matricula.curs == grup.curs,
                    Matricula.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    alumnes_pairs: list[tuple[Matricula, Alumne]] = []
    for m in matricules:
        a = await session.get(Alumne, m.alumne_id)
        if a:
            alumnes_pairs.append((m, a))
    alumnes_pairs.sort(key=lambda x: (x[1].cognoms, x[1].nom))

    rows: list[ActaAlumneRow] = []
    for matr, alumne in alumnes_pairs:
        notes_per_modul: list[ActaModulNota] = []
        for mod in moduls:
            # Load RAs + their per-alumne notes regardless (used in detail block)
            ra_detail, auto_mean = await _load_ras_with_notes(
                session,
                matricula_id=matr.id,
                modul=mod,
                avaluacio_id=avaluacio_id,
            )

            qmod = (
                await session.execute(
                    select(QualificacioModul).where(
                        QualificacioModul.matricula_id == matr.id,
                        QualificacioModul.modul_id == mod.id,
                        QualificacioModul.avaluacio_id == avaluacio_id,
                    )
                )
            ).scalar_one_or_none()

            if qmod is not None and qmod.nota is not None:
                notes_per_modul.append(
                    ActaModulNota(
                        codi=mod.codi,
                        nom=mod.nom,
                        nota=float(qmod.nota),
                        is_manual=True,
                        comentari=qmod.comentari,
                        ras=ra_detail,
                        hores=mod.hores,
                        bloquejant=mod.bloquejant,
                    )
                )
            else:
                notes_per_modul.append(
                    ActaModulNota(
                        codi=mod.codi,
                        nom=mod.nom,
                        nota=auto_mean,
                        is_manual=False,
                        comentari=None,
                        ras=ra_detail,
                        hores=mod.hores,
                        bloquejant=mod.bloquejant,
                    )
                )

        decisio, suspesos, no_qual, motiu = _derive_decisio(
            notes_per_modul,
            max_suspesos_recupera=(
                cicle.max_suspesos_recupera if cicle is not None else 2
            ),
            pct_hores_no_promociona=(
                float(cicle.pct_hores_no_promociona)
                if cicle is not None and cicle.pct_hores_no_promociona is not None
                else None
            ),
        )
        rows.append(
            ActaAlumneRow(
                cognoms=alumne.cognoms,
                nom=alumne.nom,
                dni=alumne.dni,
                ralc=alumne.ralc,
                notes_per_modul=notes_per_modul,
                decisio=decisio,
                suspesos=suspesos,
                no_qualificats=no_qual,
                motiu_decisio=motiu,
            )
        )

    # Aggregate counters
    counts = {"Apte": 0, "Recupera": 0, "No promociona": 0, "Pendent": 0}
    for r in rows:
        counts[r.decisio] = counts.get(r.decisio, 0) + 1

    ctx = {
        "centre_nom": "Institut la Ferreria",
        "data_emissio": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "data_avaluacio": (aval.data_tancament or aval.data_inici or date.today()).isoformat(),
        "curs": curs,
        "cicle": cicle,
        "grup": grup,
        "tutor": tutor,
        "tutor_signat": tutor_signat,
        "cap_estudis_signat": cap_estudis_signat,
        "director_signat": director_signat,
        "avaluacio": aval,
        "avaluacio_estat": aval.estat.value if hasattr(aval.estat, "value") else str(aval.estat),
        "moduls": moduls,
        "rows": rows,
        "counts": counts,
        "total": len(rows),
    }
    template = _jinja.get_template("pdf/acta.html")
    return template.render(**ctx)


async def render_acta_pdf(
    session: AsyncSession,
    *,
    grup_id: int,
    avaluacio_id: int,
    tutor_signat: str | None = None,
    cap_estudis_signat: str | None = None,
    director_signat: str | None = None,
) -> bytes:
    html = await render_acta_html(
        session,
        grup_id=grup_id,
        avaluacio_id=avaluacio_id,
        tutor_signat=tutor_signat,
        cap_estudis_signat=cap_estudis_signat,
        director_signat=director_signat,
    )
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
