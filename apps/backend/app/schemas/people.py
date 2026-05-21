"""Pydantic schemas for people & organisation entities."""
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.people import EstatMatricula, TipusGrup

if TYPE_CHECKING:
    pass


# --- Tutor legal ------------------------------------------------------------

class TutorLegalBase(BaseModel):
    nom: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    telefon: str | None = Field(default=None, max_length=30)


class TutorLegalCreate(TutorLegalBase):
    pass


class TutorLegalResponse(TutorLegalBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- Alumne -----------------------------------------------------------------

class AlumneBase(BaseModel):
    dni: str | None = Field(default=None, max_length=15)
    ralc: str = Field(min_length=1, max_length=25)
    nom: str = Field(min_length=1, max_length=100)
    cognoms: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    telefon: str | None = Field(default=None, max_length=30)
    data_naixement: date | None = None


class AlumneCreate(AlumneBase):
    tutors_legals: list[TutorLegalCreate] = Field(default_factory=list)


class AlumneUpdate(BaseModel):
    dni: str | None = Field(default=None, max_length=15)
    ralc: str | None = Field(default=None, min_length=1, max_length=25)
    nom: str | None = Field(default=None, min_length=1, max_length=100)
    cognoms: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    telefon: str | None = Field(default=None, max_length=30)
    data_naixement: date | None = None


class AlumneResponse(AlumneBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tutors_legals: list[TutorLegalResponse] = []


# --- Grup classe ------------------------------------------------------------

class GrupClasseBase(BaseModel):
    codi: str = Field(min_length=1, max_length=30)
    curs_acad_id: int
    cicle_id: int
    curs: int = Field(ge=1, le=4)
    tutor_user_id: int | None = None


class GrupClasseCreate(GrupClasseBase):
    pass


class GrupClasseUpdate(BaseModel):
    codi: str | None = Field(default=None, min_length=1, max_length=30)
    curs_acad_id: int | None = None
    cicle_id: int | None = None
    curs: int | None = Field(default=None, ge=1, le=4)
    tutor_user_id: int | None = None


class GrupClasseResponse(GrupClasseBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cicle_codi: str | None = None
    curs_acad_nom: str | None = None
    tutor_nom_complet: str | None = None


# --- Matrícula --------------------------------------------------------------

class MatriculaBase(BaseModel):
    alumne_id: int
    grup_id: int
    cicle_id: int
    curs: int = Field(ge=1, le=4)
    curs_acad_id: int
    tipus: TipusGrup = TipusGrup.PRIMARI
    estat: EstatMatricula = EstatMatricula.ACTIU


class MatriculaCreate(MatriculaBase):
    pass


class MatriculaUpdate(BaseModel):
    grup_id: int | None = None
    estat: EstatMatricula | None = None


class MatriculaResponse(MatriculaBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: int


# --- Assignació docent ------------------------------------------------------

class AssignacioDocentBase(BaseModel):
    user_id: int
    grup_id: int
    modul_id: int
    curs_acad_id: int


class AssignacioDocentCreate(AssignacioDocentBase):
    pass


class AssignacioDocentResponse(AssignacioDocentBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
