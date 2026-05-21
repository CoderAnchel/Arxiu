"""Pydantic schemas for avaluacions + qualificacions."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.grading import EstatAvaluacio


# --- Avaluació --------------------------------------------------------------

class AvaluacioBase(BaseModel):
    curs_acad_id: int
    nom: str = Field(min_length=1, max_length=100)
    ordre: int = Field(ge=1, le=20)
    data_inici: date | None = None


class AvaluacioCreate(AvaluacioBase):
    pass


class AvaluacioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: int
    curs_acad_id: int
    nom: str
    ordre: int
    estat: EstatAvaluacio
    data_inici: date | None
    data_tancament: date | None


class AvaluacioTransitionRequest(BaseModel):
    target: EstatAvaluacio


# --- Grade matrix (read-side for the spreadsheet) --------------------------

class GradeMatrixAlumne(BaseModel):
    matricula_id: int
    alumne_id: int
    nom: str
    cognoms: str
    dni: str | None
    ralc: str


class GradeMatrixRa(BaseModel):
    id: int
    ordre: int
    codi: str
    descripcio: str
    pes: Decimal


class GradeMatrixCell(BaseModel):
    matricula_id: int
    ra_id: int
    nota: float | None
    comentari: str | None


class GradeMatrixModulCell(BaseModel):
    """Manual mòdul-level override (the final note that bypasses RA mean)."""
    matricula_id: int
    nota: float | None
    comentari: str | None


class GradeMatrixResponse(BaseModel):
    grup_id: int
    modul_id: int
    avaluacio_id: int
    avaluacio_estat: EstatAvaluacio
    can_edit: bool
    alumnes: list[GradeMatrixAlumne]
    ras: list[GradeMatrixRa]
    cells: list[GradeMatrixCell]
    # Manual modul-level overrides for this (modul, avaluacio): empty if none.
    modul_cells: list[GradeMatrixModulCell] = []


# --- Bulk PATCH -------------------------------------------------------------

class QualifRaPatch(BaseModel):
    matricula_id: int
    ra_id: int
    nota: Decimal | None = Field(default=None, ge=0, le=10)
    comentari: str | None = Field(default=None, max_length=2000)


class BulkQualifRaPatch(BaseModel):
    avaluacio_id: int
    patches: list[QualifRaPatch] = Field(min_length=1, max_length=2000)


class QualifRaPatchResult(BaseModel):
    matricula_id: int
    ra_id: int
    ok: bool
    error: str | None = None


class BulkQualifRaPatchResponse(BaseModel):
    results: list[QualifRaPatchResult]
    saved: int
    failed: int


# --- Mòdul-level bulk PATCH (manual final-note overrides) -------------------

class QualifModulPatch(BaseModel):
    matricula_id: int
    nota: Decimal | None = Field(default=None, ge=0, le=10)
    comentari: str | None = Field(default=None, max_length=2000)


class BulkQualifModulPatch(BaseModel):
    avaluacio_id: int
    modul_id: int
    patches: list[QualifModulPatch] = Field(min_length=1, max_length=1000)


class QualifModulPatchResult(BaseModel):
    matricula_id: int
    ok: bool
    error: str | None = None


class BulkQualifModulPatchResponse(BaseModel):
    results: list[QualifModulPatchResult]
    saved: int
    failed: int
