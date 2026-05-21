"""Schemas for butlletins + enviaments."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enviaments import EstatEnviament, TipusEnviament


# --- Butlletí generation ---------------------------------------------------

class ButlletiOptsSchema(BaseModel):
    detall_ra: bool = True
    comentaris: bool = True
    distribucio_grup: bool = False
    signatura: bool = True
    logo_centre: bool = True


class ButlletiGenerateRequest(BaseModel):
    avaluacio_id: int
    alumne_ids: list[int] = Field(min_length=1, max_length=200)
    opts: ButlletiOptsSchema = Field(default_factory=ButlletiOptsSchema)


class ButlletiGenerateResultRow(BaseModel):
    alumne_id: int
    ok: bool
    error: str | None = None
    filename: str | None = None
    size_bytes: int | None = None


class ButlletiGenerateResponse(BaseModel):
    results: list[ButlletiGenerateResultRow]
    generated: int
    failed: int


# --- Butlletí email -------------------------------------------------------

class ButlletiSendRequest(BaseModel):
    avaluacio_id: int
    alumne_ids: list[int] = Field(min_length=1, max_length=500)
    send_to: list[str] = Field(
        default_factory=lambda: ["alumne", "tutors"],
        description="Subset of {'alumne','tutors'}",
    )
    opts: ButlletiOptsSchema = Field(default_factory=ButlletiOptsSchema)


class ButlletiSendResultRow(BaseModel):
    alumne_id: int
    destinatari_email: str
    enviament_id: int
    estat: EstatEnviament
    error: str | None = None


class ButlletiSendResponse(BaseModel):
    results: list[ButlletiSendResultRow]
    sent: int
    failed: int


# --- Enviaments listing ---------------------------------------------------

class EnviamentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: int
    alumne_id: int | None
    destinatari_email: str
    tipus: TipusEnviament
    assumpte: str
    estat: EstatEnviament
    error_msg: str | None
    queued_at: datetime
    sent_at: datetime | None
    opened_at: datetime | None
    avaluacio_id: int | None
    adjunt_filename: str | None
