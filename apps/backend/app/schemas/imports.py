"""Schemas for /imports + /audit-logs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.imports import EstatImport, TipusImport


class ImportPreviewRow(BaseModel):
    row: int
    data: dict[str, Any]
    errors: list[str] = []
    warnings: list[str] = []


class ImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)
    id: int
    tipus: TipusImport
    fitxer_nom: str | None
    user_id: int | None
    total: int
    ok: int
    errors: int
    estat: EstatImport
    created_at: datetime
    completed_at: datetime | None


class ImportPreviewResponse(ImportResponse):
    preview: list[ImportPreviewRow] = []


class ImportConfirmResponse(ImportResponse):
    result: dict[str, Any] | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    user_agent: str | None
    created_at: datetime
