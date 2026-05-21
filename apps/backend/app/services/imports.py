"""Excel/CSV import service. Two-step flow:

  1. POST /imports/alumnes (upload)  → server saves the file, parses + validates,
     returns an Import row in `pending` status with the parsed preview.
  2. POST /imports/{id}/confirm       → server re-parses, commits valid rows,
     transitions to `completed` (or `failed` on hard errors).

Supports .xlsx and .csv. Headers are matched case-insensitively against a
canonical column-name set per import type, with common aliases.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import openpyxl
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import Conflict, NotFound, ValidationError
from app.models.catalog import Modul, Ra
from app.models.grading import Avaluacio, QualificacioRa
from app.models.imports import EstatImport, Import, TipusImport
from app.models.people import Alumne, Matricula, TutorLegal
from app.services import audit


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

ALUMNE_COLUMNS: dict[str, list[str]] = {
    # canonical → list of accepted aliases (all lowercase, accent-stripped)
    "ralc":          ["ralc", "nia", "ralc/nia", "nia/ralc"],
    "dni":           ["dni", "nie", "dni/nie", "nif"],
    "nom":           ["nom", "name"],
    "cognoms":       ["cognoms", "apellidos", "surname"],
    "email":         ["email", "email alumne", "correu", "correu alumne"],
    "telefon":       ["telefon", "telefono", "phone", "tel"],
    "data_naixement":["data naixement", "data de naixement", "naixement", "fecha nacimiento", "birth"],
    "tutor_email":   ["email tutor", "tutor email", "email tutor/a"],
    "tutor_nom":     ["nom tutor", "tutor nom", "tutor"],
}


# Notes import: row identifier + per-RA value columns.
# RA columns are matched by their header being either "RA1", "RA2"… or the
# exact `codi` of the RA (case-insensitive).
NOTES_ID_COLUMNS: dict[str, list[str]] = {
    "ralc": ["ralc", "nia", "ralc/nia", "nia/ralc"],
    "dni":  ["dni", "nie", "dni/nie", "nif"],
    "nom":  ["nom", "alumne", "name", "nom alumne"],
}


def _normalise(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove punctuation."""
    s = s.strip().lower()
    s = (
        s.replace("à", "a").replace("á", "a").replace("ä", "a").replace("â", "a")
        .replace("è", "e").replace("é", "e").replace("ë", "e").replace("ê", "e")
        .replace("ì", "i").replace("í", "i").replace("ï", "i").replace("î", "i")
        .replace("ò", "o").replace("ó", "o").replace("ö", "o").replace("ô", "o")
        .replace("ù", "u").replace("ú", "u").replace("ü", "u").replace("û", "u")
        .replace("ç", "c").replace("ñ", "n")
    )
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[._\-/]", " ", s)
    return s


def _build_col_map(headers: list[str], canonical: dict[str, list[str]]) -> dict[str, int]:
    """Returns canonical_name → column_index. Missing canonicals are absent."""
    out: dict[str, int] = {}
    for idx, raw in enumerate(headers):
        if not raw:
            continue
        norm = _normalise(str(raw))
        for canonical_name, aliases in canonical.items():
            if canonical_name in out:
                continue
            if any(_normalise(a) == norm for a in aliases):
                out[canonical_name] = idx
                break
    return out


# ---------------------------------------------------------------------------
# Parse — file → list of dict-rows
# ---------------------------------------------------------------------------

def _read_xlsx(path: Path) -> list[list[Any]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = [list(r) for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    wb.close()
    return rows


def _read_csv(path: Path) -> list[list[Any]]:
    with path.open("rb") as fh:
        raw = fh.read()
    # Detect BOM + decode UTF-8 (the spec says UTF-8 only)
    text = raw.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # fallback to comma
    reader = csv.reader(io.StringIO(text), dialect=dialect)
    return [r for r in reader if any(c.strip() for c in r)]


def _read(path: Path) -> list[list[Any]]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        return _read_xlsx(path)
    if suffix in {".csv", ".tsv", ".txt"}:
        return _read_csv(path)
    raise ValidationError(f"unsupported file extension: {suffix}")


# ---------------------------------------------------------------------------
# Validators per import type
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class ParsedRow:
    row_number: int
    data: dict[str, Any]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


_RE_DNI = re.compile(r"^[0-9]{7,8}[A-Z]$")
_RE_NIE = re.compile(r"^[XYZ][0-9]{7}[A-Z]$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _coerce_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_alumnes(file_path: Path) -> tuple[list[ParsedRow], list[str]]:
    """Returns (rows, file_level_errors)."""
    table = _read(file_path)
    if not table:
        return [], ["fitxer buit"]
    headers = [str(c) if c is not None else "" for c in table[0]]
    cmap = _build_col_map(headers, ALUMNE_COLUMNS)

    if "ralc" not in cmap:
        return [], ["columna obligatòria 'RALC' (o 'NIA') no trobada"]
    if "nom" not in cmap or "cognoms" not in cmap:
        return [], ["columnes obligatòries 'Nom' i 'Cognoms' no trobades"]

    out: list[ParsedRow] = []
    seen_ralcs: set[str] = set()

    for i, row in enumerate(table[1:], start=2):
        def cell(name: str) -> Any:
            idx = cmap.get(name)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        ralc_raw = cell("ralc")
        ralc = str(ralc_raw).strip() if ralc_raw is not None else ""
        nom = (str(cell("nom") or "")).strip()
        cognoms = (str(cell("cognoms") or "")).strip()
        dni_raw = cell("dni")
        dni = (str(dni_raw or "")).strip().upper() or None

        email_raw = cell("email")
        email = (str(email_raw or "")).strip().lower() or None
        tel = (str(cell("telefon") or "")).strip() or None
        data_naix = _coerce_date(cell("data_naixement"))
        tutor_email = (str(cell("tutor_email") or "")).strip().lower() or None
        tutor_nom = (str(cell("tutor_nom") or "")).strip() or None

        pr = ParsedRow(
            row_number=i,
            data={
                "ralc": ralc,
                "dni": dni,
                "nom": nom,
                "cognoms": cognoms,
                "email": email,
                "telefon": tel,
                "data_naixement": data_naix.isoformat() if data_naix else None,
                "tutor_email": tutor_email,
                "tutor_nom": tutor_nom,
            },
        )

        if not ralc:
            pr.errors.append("RALC buit")
        elif ralc in seen_ralcs:
            pr.errors.append(f"RALC duplicat al fitxer ({ralc})")
        else:
            seen_ralcs.add(ralc)

        if not nom:
            pr.errors.append("nom buit")
        if not cognoms:
            pr.errors.append("cognoms buits")

        if dni and not (_RE_DNI.match(dni) or _RE_NIE.match(dni)):
            pr.warnings.append(f"format DNI/NIE inusual: {dni}")
        if email and not _RE_EMAIL.match(email):
            pr.errors.append(f"email no vàlid: {email}")
        if tutor_email and not _RE_EMAIL.match(tutor_email):
            pr.warnings.append(f"email del tutor no vàlid: {tutor_email}")
        if cell("data_naixement") and data_naix is None:
            pr.warnings.append(f"data naixement il·legible: {cell('data_naixement')}")

        out.append(pr)

    return out, []


# ---------------------------------------------------------------------------
# High-level flow: save file → preview → confirm
# ---------------------------------------------------------------------------

def _storage_dir() -> Path:
    base = get_settings().storage_root / "imports"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _save_upload(*, content: bytes, filename: str) -> Path:
    safe = re.sub(r"[^\w.\-]", "_", filename)
    target = _storage_dir() / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{safe}"
    target.write_bytes(content)
    return target


async def parse_notes(
    file_path: Path,
    *,
    modul_id: int,
    session: AsyncSession,
) -> tuple[list[ParsedRow], list[str]]:
    """Parse a notes Excel/CSV against a specific mòdul. Each row = one alumne.
    Columns: DNI or RALC + one column per RA of the mòdul (header = RA codi or "RA1", "RA2"...)."""
    table = _read(file_path)
    if not table:
        return [], ["fitxer buit"]

    headers = [str(c) if c is not None else "" for c in table[0]]
    id_map = _build_col_map(headers, NOTES_ID_COLUMNS)

    if "ralc" not in id_map and "dni" not in id_map:
        return [], ["columna obligatòria RALC o DNI no trobada"]

    ras = list(
        (
            await session.execute(
                select(Ra).where(Ra.modul_id == modul_id, Ra.deleted_at.is_(None)).order_by(Ra.ordre)
            )
        )
        .scalars()
        .all()
    )
    if not ras:
        return [], [f"el mòdul #{modul_id} no té RAs definits"]

    ra_by_codi = {_normalise(r.codi): r for r in ras}
    ra_by_ordre = {f"ra{r.ordre}": r for r in ras}

    col_to_ra: dict[int, Ra] = {}
    for idx, raw in enumerate(headers):
        if not raw:
            continue
        norm = _normalise(str(raw))
        if norm in ra_by_codi:
            col_to_ra[idx] = ra_by_codi[norm]
        elif norm in ra_by_ordre:
            col_to_ra[idx] = ra_by_ordre[norm]

    if not col_to_ra:
        return [], [
            "no s'ha trobat cap columna de notes; esperat: "
            + ", ".join(r.codi for r in ras)
        ]

    out: list[ParsedRow] = []
    for i, row in enumerate(table[1:], start=2):
        def cell(name: str) -> Any:
            idx = id_map.get(name)
            if idx is None or idx >= len(row):
                return None
            return row[idx]

        ralc = (str(cell("ralc") or "")).strip() or None
        dni = (str(cell("dni") or "")).strip().upper() or None

        ra_notes: dict[str, Any] = {}
        for col_idx, ra in col_to_ra.items():
            v = row[col_idx] if col_idx < len(row) else None
            ra_notes[ra.codi] = v

        pr = ParsedRow(
            row_number=i,
            data={"ralc": ralc, "dni": dni, "ra_notes": ra_notes},
        )

        if not ralc and not dni:
            pr.errors.append("fila sense RALC ni DNI")

        clean_notes: dict[int, float | None] = {}
        for col_idx, ra in col_to_ra.items():
            v = row[col_idx] if col_idx < len(row) else None
            if v is None or (isinstance(v, str) and not v.strip()):
                clean_notes[ra.id] = None
                continue
            try:
                f = float(str(v).replace(",", "."))
            except ValueError:
                pr.errors.append(f"{ra.codi}: valor no numèric '{v}'")
                continue
            if f < 0 or f > 10:
                pr.errors.append(
                    f"{ra.codi}: nota {f} fora de rang (vàlid 0-10)"
                )
                continue
            clean_notes[ra.id] = round(f, 2)

        pr.data["_clean_notes_by_ra_id"] = clean_notes
        out.append(pr)

    return out, []


async def create_import_preview(
    session: AsyncSession,
    *,
    tipus: TipusImport,
    filename: str,
    content: bytes,
    actor_id: int,
    modul_id: int | None = None,
    avaluacio_id: int | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[Import, list[ParsedRow]]:
    if len(content) > 5 * 1024 * 1024:
        raise ValidationError("fitxer massa gran (>5 MB)")

    saved = _save_upload(content=content, filename=filename)

    if tipus == TipusImport.ALUMNES:
        rows, file_errors = parse_alumnes(saved)
        log_extra: dict[str, Any] = {}
    elif tipus == TipusImport.NOTES:
        if modul_id is None or avaluacio_id is None:
            raise ValidationError("notes import requires modul_id and avaluacio_id")
        rows, file_errors = await parse_notes(saved, modul_id=modul_id, session=session)
        log_extra = {"modul_id": modul_id, "avaluacio_id": avaluacio_id}
    else:
        raise NotFound(f"importer for {tipus} not implemented yet")

    if file_errors:
        raise ValidationError("; ".join(file_errors))

    imp = Import(
        tipus=tipus,
        fitxer_nom=filename,
        fitxer_path=str(saved),
        user_id=actor_id,
        total=len(rows),
        ok=sum(1 for r in rows if r.ok),
        errors=sum(1 for r in rows if not r.ok),
        log={
            **log_extra,
            "preview": [
                {
                    "row": r.row_number,
                    "data": {k: v for k, v in r.data.items() if not k.startswith("_")},
                    "errors": r.errors,
                    "warnings": r.warnings,
                }
                for r in rows
            ],
        },
        estat=EstatImport.PENDING,
    )
    session.add(imp)
    await session.flush()

    await audit.record(
        session,
        action="import_uploaded",
        entity="import",
        entity_id=imp.id,
        user_id=actor_id,
        after={"tipus": tipus.value, "total": imp.total, "ok": imp.ok, "errors": imp.errors},
        ip=ip,
        user_agent=user_agent,
    )
    return imp, rows


async def confirm_import(
    session: AsyncSession,
    *,
    import_id: int,
    actor_id: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Import:
    imp = await session.get(Import, import_id)
    if imp is None:
        raise NotFound("import not found")
    if imp.estat != EstatImport.PENDING:
        raise Conflict(f"import already in state '{imp.estat.value}'")
    if not imp.fitxer_path or not Path(imp.fitxer_path).exists():
        raise ValidationError("import file no longer available on disk")

    imp.estat = EstatImport.PROCESSING
    await session.flush()

    saved = Path(imp.fitxer_path)
    if imp.tipus == TipusImport.ALUMNES:
        rows, _ = parse_alumnes(saved)
        outcome = await _commit_alumnes(session, rows, imp=imp, actor_id=actor_id)
    elif imp.tipus == TipusImport.NOTES:
        log = imp.log or {}
        modul_id = log.get("modul_id")
        avaluacio_id = log.get("avaluacio_id")
        if not modul_id or not avaluacio_id:
            raise ValidationError("import metadata missing modul_id/avaluacio_id")
        rows, _ = await parse_notes(saved, modul_id=modul_id, session=session)
        outcome = await _commit_notes(
            session, rows, imp=imp, actor_id=actor_id, avaluacio_id=avaluacio_id
        )
    else:
        raise NotFound(f"importer for {imp.tipus.value} not implemented yet")

    imp.estat = EstatImport.COMPLETED
    imp.completed_at = datetime.now(timezone.utc)
    imp.ok = outcome["created"] + outcome["updated"]
    imp.errors = outcome["errors"]
    imp.log = {
        **(imp.log or {}),
        "result": outcome,
    }

    await audit.record(
        session,
        action="import_confirmed",
        entity="import",
        entity_id=imp.id,
        user_id=actor_id,
        after={"created": outcome["created"], "updated": outcome["updated"], "errors": outcome["errors"]},
        ip=ip,
        user_agent=user_agent,
    )
    return imp


async def _commit_alumnes(
    session: AsyncSession, rows: Iterable[ParsedRow], *, imp: Import, actor_id: int
) -> dict[str, Any]:
    created = 0
    updated = 0
    errors_count = 0
    error_log: list[dict[str, Any]] = []

    for r in rows:
        if not r.ok:
            errors_count += 1
            error_log.append({"row": r.row_number, "errors": r.errors})
            continue

        d = r.data
        # Try to find by RALC first, else by DNI
        existing = (
            await session.execute(select(Alumne).where(Alumne.ralc == d["ralc"]))
        ).scalar_one_or_none()

        if existing is None and d.get("dni"):
            existing = (
                await session.execute(select(Alumne).where(Alumne.dni == d["dni"]))
            ).scalar_one_or_none()

        if existing is not None:
            existing.nom = d["nom"]
            existing.cognoms = d["cognoms"]
            if d.get("dni"):
                existing.dni = d["dni"]
            if d.get("email"):
                existing.email = d["email"]
            if d.get("telefon"):
                existing.telefon = d["telefon"]
            if d.get("data_naixement"):
                existing.data_naixement = _coerce_date(d["data_naixement"])
            try:
                await session.flush()
                updated += 1
                # Add tutor if email present and not already linked
                if d.get("tutor_email"):
                    has_tutor = any(t.email == d["tutor_email"] for t in existing.tutors_legals)
                    if not has_tutor:
                        existing.tutors_legals.append(
                            TutorLegal(
                                nom=d.get("tutor_nom") or "Tutor/a",
                                email=d["tutor_email"],
                            )
                        )
                        await session.flush()
            except IntegrityError as exc:
                await session.rollback()
                errors_count += 1
                error_log.append({"row": r.row_number, "errors": [f"db: {str(exc)[:100]}"]})
            continue

        try:
            alumne = Alumne(
                ralc=d["ralc"],
                dni=d.get("dni"),
                nom=d["nom"],
                cognoms=d["cognoms"],
                email=d.get("email"),
                telefon=d.get("telefon"),
                data_naixement=_coerce_date(d.get("data_naixement")),
            )
            if d.get("tutor_email"):
                alumne.tutors_legals.append(
                    TutorLegal(
                        nom=d.get("tutor_nom") or "Tutor/a",
                        email=d["tutor_email"],
                    )
                )
            session.add(alumne)
            await session.flush()
            created += 1
        except IntegrityError as exc:
            await session.rollback()
            errors_count += 1
            error_log.append({"row": r.row_number, "errors": [f"db: {str(exc)[:100]}"]})

    return {
        "created": created,
        "updated": updated,
        "errors": errors_count,
        "error_rows": error_log,
    }


async def _commit_notes(
    session: AsyncSession,
    rows: Iterable[ParsedRow],
    *,
    imp: Import,
    actor_id: int,
    avaluacio_id: int,
) -> dict[str, Any]:
    """Persist qualificacions_ra rows from a parsed notes file."""
    avaluacio = await session.get(Avaluacio, avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise NotFound("avaluacio not found")

    # Defensive: ensure the import's mòdul exists and grab its curs so we can
    # reject any matrícula whose curs doesn't match (a 1r-curs student can't
    # receive a 2n-curs module's notes — the structural validation we enforce
    # everywhere else applies here too).
    modul_id = (imp.log or {}).get("modul_id")
    modul = await session.get(Modul, modul_id) if modul_id is not None else None

    created = 0
    updated = 0
    errors_count = 0
    error_log: list[dict[str, Any]] = []

    for r in rows:
        if not r.ok:
            errors_count += 1
            error_log.append({"row": r.row_number, "errors": r.errors})
            continue

        d = r.data
        clean = d.get("_clean_notes_by_ra_id", {})

        alumne: Alumne | None = None
        if d.get("ralc"):
            alumne = (
                await session.execute(select(Alumne).where(Alumne.ralc == d["ralc"]))
            ).scalar_one_or_none()
        if alumne is None and d.get("dni"):
            alumne = (
                await session.execute(select(Alumne).where(Alumne.dni == d["dni"]))
            ).scalar_one_or_none()
        if alumne is None:
            errors_count += 1
            error_log.append({"row": r.row_number, "errors": ["alumne no trobat"]})
            continue

        matr = (
            await session.execute(
                select(Matricula).where(
                    Matricula.alumne_id == alumne.id,
                    Matricula.curs_acad_id == avaluacio.curs_acad_id,
                    Matricula.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if matr is None:
            errors_count += 1
            error_log.append({"row": r.row_number, "errors": ["matrícula no trobada en aquest curs"]})
            continue

        if modul is not None and matr.curs != modul.curs:
            errors_count += 1
            error_log.append(
                {
                    "row": r.row_number,
                    "errors": [
                        f"matrícula de {matr.curs}r curs no coincideix amb mòdul {modul.codi} ({modul.curs}r)"
                    ],
                }
            )
            continue

        for ra_id, nota in clean.items():
            stmt = select(QualificacioRa).where(
                QualificacioRa.matricula_id == matr.id,
                QualificacioRa.ra_id == ra_id,
                QualificacioRa.avaluacio_id == avaluacio_id,
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing is None:
                session.add(
                    QualificacioRa(
                        matricula_id=matr.id,
                        ra_id=ra_id,
                        avaluacio_id=avaluacio_id,
                        nota=nota,
                        professor_user_id=actor_id,
                    )
                )
                created += 1
            else:
                existing.nota = nota
                existing.professor_user_id = actor_id
                updated += 1
        await session.flush()

    await audit.record(
        session,
        action="notes_imported",
        entity="avaluacio",
        entity_id=avaluacio_id,
        user_id=actor_id,
        after={"created": created, "updated": updated, "errors": errors_count},
    )
    return {
        "created": created,
        "updated": updated,
        "errors": errors_count,
        "error_rows": error_log,
    }
