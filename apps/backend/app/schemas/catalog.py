"""Pydantic schemas for catalog entities."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.catalog import Nivell

# --- Família ----------------------------------------------------------------

class FamiliaBase(BaseModel):
    codi: str = Field(min_length=1, max_length=20)
    nom: str = Field(min_length=1, max_length=150)


class FamiliaCreate(FamiliaBase):
    pass


class FamiliaUpdate(BaseModel):
    codi: str | None = Field(default=None, min_length=1, max_length=20)
    nom: str | None = Field(default=None, min_length=1, max_length=150)


class FamiliaResponse(FamiliaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- Cicle ------------------------------------------------------------------

class CicleBase(BaseModel):
    codi: str = Field(min_length=1, max_length=20)
    nom: str = Field(min_length=1, max_length=255)
    familia_id: int | None = None
    nivell: Nivell
    durada: int = Field(default=2, ge=1, le=4)
    # Política de junta
    max_suspesos_recupera: int = Field(default=2, ge=0, le=20)
    pct_hores_no_promociona: Decimal | None = Field(default=None, ge=0, le=100)


class CicleCreate(CicleBase):
    pass


class CicleUpdate(BaseModel):
    codi: str | None = Field(default=None, min_length=1, max_length=20)
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    familia_id: int | None = None
    nivell: Nivell | None = None
    durada: int | None = Field(default=None, ge=1, le=4)
    max_suspesos_recupera: int | None = Field(default=None, ge=0, le=20)
    pct_hores_no_promociona: Decimal | None = Field(default=None, ge=0, le=100)


class CicleResponse(CicleBase):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: int


class CicleDetailResponse(CicleResponse):
    """Cicle with its mòduls + RAs nested for the Currículums page."""
    moduls: list[ModulResponse] = []  # type: ignore[name-defined]


# --- Mòdul ------------------------------------------------------------------

class ModulBase(BaseModel):
    cicle_id: int
    codi: str = Field(min_length=1, max_length=20)
    nom: str = Field(min_length=1, max_length=255)
    curs: int = Field(ge=1, le=4)
    hores: int = Field(default=99, ge=0, le=2000)
    bloquejant: bool = False


class ModulCreate(ModulBase):
    pass


class ModulUpdate(BaseModel):
    codi: str | None = Field(default=None, min_length=1, max_length=20)
    nom: str | None = Field(default=None, min_length=1, max_length=255)
    curs: int | None = Field(default=None, ge=1, le=4)
    hores: int | None = Field(default=None, ge=0, le=2000)
    bloquejant: bool | None = None


class ModulResponse(ModulBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ras: list[RaResponse] = []  # type: ignore[name-defined]


# --- RA ---------------------------------------------------------------------

class RaBase(BaseModel):
    modul_id: int
    ordre: int = Field(ge=1, le=20)
    codi: str = Field(min_length=1, max_length=20)
    descripcio: str = Field(min_length=1, max_length=2000)
    pes: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class RaCreate(RaBase):
    pass


class RaUpdate(BaseModel):
    ordre: int | None = Field(default=None, ge=1, le=20)
    codi: str | None = Field(default=None, min_length=1, max_length=20)
    descripcio: str | None = Field(default=None, min_length=1, max_length=2000)
    pes: Decimal | None = Field(default=None, ge=0, le=100)


class RaResponse(RaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# Resolve forward refs (Pydantic v2)
ModulResponse.model_rebuild()
CicleDetailResponse.model_rebuild()


# --- Curs acadèmic ----------------------------------------------------------

class CursAcademicBase(BaseModel):
    nom: str = Field(min_length=1, max_length=20)
    actiu: bool = False
    data_inici: date | None = None
    data_fi: date | None = None


class CursAcademicCreate(CursAcademicBase):
    pass


class CursAcademicUpdate(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=20)
    actiu: bool | None = None
    data_inici: date | None = None
    data_fi: date | None = None


class CursAcademicResponse(CursAcademicBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CursAcademicCloneRequest(BaseModel):
    nom: str = Field(min_length=1, max_length=20)
    set_active: bool = False
    clone_grups: bool = True
    clone_assignacions: bool = True
    data_inici: date | None = None
    data_fi: date | None = None
