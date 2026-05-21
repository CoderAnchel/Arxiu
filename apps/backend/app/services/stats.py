"""Pedagogic statistics — distributions and aggregates per grup × mòdul × avaluació.

These are computed on-the-fly from `qualificacions_ra` and `qualificacions_modul`.
The dataset is small (one school, a few hundred students per cohort), so no
caching is needed: a typical query returns in <50ms.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.catalog import Modul, Ra
from app.models.grading import Avaluacio, QualificacioModul, QualificacioRa
from app.models.people import GrupClasse, Matricula


# 11 buckets: <2, [2,3), [3,4), [4,5), [5,6), [6,7), [7,8), [8,9), [9,10), 10
HIST_BUCKETS: list[tuple[float, float, str]] = [
    (0.0, 2.0, "0-2"),
    (2.0, 3.0, "2-3"),
    (3.0, 4.0, "3-4"),
    (4.0, 5.0, "4-5"),
    (5.0, 6.0, "5-6"),
    (6.0, 7.0, "6-7"),
    (7.0, 8.0, "7-8"),
    (8.0, 9.0, "8-9"),
    (9.0, 10.0, "9-10"),
    (10.0, 10.01, "10"),
]


def _bucket_label(n: float) -> str:
    for lo, hi, label in HIST_BUCKETS:
        if lo <= n < hi:
            return label
    return "10"


@dataclass(frozen=True, slots=True)
class HistogramBin:
    label: str
    lo: float
    hi: float
    count: int


@dataclass(frozen=True, slots=True)
class RaStat:
    ra_id: int
    codi: str
    descripcio: str
    pes: float
    avg: float | None
    suspesos: int
    aprovats: int
    no_qualificats: int


@dataclass(frozen=True, slots=True)
class ModulStats:
    modul_id: int
    grup_id: int
    avaluacio_id: int
    n_alumnes: int
    n_qualificats: int   # alumnes amb almenys una nota
    n_complerts: int     # alumnes amb totes les RAs qualificades
    avg_final: float | None
    median_final: float | None
    pct_aprovats: float | None
    histogram: list[HistogramBin]
    ras: list[RaStat]


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


async def compute_modul_stats(
    session: AsyncSession,
    *,
    grup_id: int,
    modul_id: int,
    avaluacio_id: int,
) -> ModulStats:
    grup = await session.get(GrupClasse, grup_id)
    modul = await session.get(Modul, modul_id)
    aval = await session.get(Avaluacio, avaluacio_id)
    if grup is None or modul is None or aval is None:
        raise NotFound("grup / mòdul / avaluació no trobat")

    matricules = list(
        (
            await session.execute(
                select(Matricula).where(
                    Matricula.grup_id == grup_id,
                    Matricula.curs == modul.curs,
                    Matricula.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    matr_ids = [m.id for m in matricules]
    n_alumnes = len(matricules)

    ras = list(
        (
            await session.execute(
                select(Ra)
                .where(Ra.modul_id == modul_id, Ra.deleted_at.is_(None))
                .order_by(Ra.ordre)
            )
        )
        .scalars()
        .all()
    )

    qras: list[QualificacioRa] = []
    qmoduls: list[QualificacioModul] = []
    if matr_ids and ras:
        qras = list(
            (
                await session.execute(
                    select(QualificacioRa).where(
                        QualificacioRa.matricula_id.in_(matr_ids),
                        QualificacioRa.avaluacio_id == avaluacio_id,
                        QualificacioRa.ra_id.in_([r.id for r in ras]),
                    )
                )
            )
            .scalars()
            .all()
        )
    if matr_ids:
        qmoduls = list(
            (
                await session.execute(
                    select(QualificacioModul).where(
                        QualificacioModul.matricula_id.in_(matr_ids),
                        QualificacioModul.modul_id == modul_id,
                        QualificacioModul.avaluacio_id == avaluacio_id,
                    )
                )
            )
            .scalars()
            .all()
        )

    # Index RA notes per (matricula, ra) for the final calculation
    ra_by: dict[tuple[int, int], Decimal] = {
        (q.matricula_id, q.ra_id): q.nota for q in qras if q.nota is not None
    }
    modul_manual: dict[int, Decimal] = {
        q.matricula_id: q.nota for q in qmoduls if q.nota is not None
    }

    # Compute final per alumne (manual override else weighted mean)
    finals: list[float] = []
    n_qualificats = 0
    n_complerts = 0
    for m in matricules:
        ra_count = sum(1 for r in ras if (m.id, r.id) in ra_by)
        if ra_count > 0:
            n_qualificats += 1
        manual = modul_manual.get(m.id)
        if manual is not None:
            finals.append(float(manual))
            n_complerts += 1
            continue
        if ra_count == len(ras) and ras:
            tw = sum(float(r.pes) for r in ras if r.pes is not None) or 1.0
            weighted = sum(
                float(ra_by[(m.id, r.id)]) * float(r.pes or 0) for r in ras
            )
            finals.append(round(weighted / tw, 2))
            n_complerts += 1

    if finals:
        avg_final = round(sum(finals) / len(finals), 2)
        median_final = _percentile(finals, 0.5)
        if median_final is not None:
            median_final = round(median_final, 2)
        n_aprovats = sum(1 for f in finals if f >= 5)
        pct_aprovats = round(100 * n_aprovats / len(finals), 1)
    else:
        avg_final = None
        median_final = None
        pct_aprovats = None

    # Histogram of finals
    counter: Counter[str] = Counter(_bucket_label(f) for f in finals)
    histogram = [
        HistogramBin(label=label, lo=lo, hi=hi, count=counter.get(label, 0))
        for lo, hi, label in HIST_BUCKETS
    ]

    # Per-RA stats
    ra_rows: list[RaStat] = []
    for r in ras:
        notes = [
            float(ra_by[(m.id, r.id)]) for m in matricules if (m.id, r.id) in ra_by
        ]
        if notes:
            avg = round(sum(notes) / len(notes), 2)
            suspesos = sum(1 for n in notes if n < 5)
            aprovats = len(notes) - suspesos
        else:
            avg = None
            suspesos = 0
            aprovats = 0
        no_qual = n_alumnes - len(notes)
        ra_rows.append(
            RaStat(
                ra_id=r.id,
                codi=r.codi,
                descripcio=r.descripcio,
                pes=float(r.pes) if r.pes is not None else 0.0,
                avg=avg,
                suspesos=suspesos,
                aprovats=aprovats,
                no_qualificats=no_qual,
            )
        )

    return ModulStats(
        modul_id=modul_id,
        grup_id=grup_id,
        avaluacio_id=avaluacio_id,
        n_alumnes=n_alumnes,
        n_qualificats=n_qualificats,
        n_complerts=n_complerts,
        avg_final=avg_final,
        median_final=median_final,
        pct_aprovats=pct_aprovats,
        histogram=histogram,
        ras=ra_rows,
    )
