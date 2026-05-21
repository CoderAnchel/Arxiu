"""Admin settings endpoints — SMTP configuration manageable from the UI."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.v1.deps import AdminUser, DbSession, get_request_metadata
from app.services import audit, settings as settings_service
from app.services.email import _send_message
from app.services.settings import SmtpConfig
from fastapi import Request

router = APIRouter(prefix="/settings", tags=["settings"])


class SmtpReadResponse(BaseModel):
    """SMTP config as returned to admins. The password is NEVER included —
    only a flag indicating whether one is currently stored."""
    smtp_host: str | None
    smtp_port: int | None
    smtp_username: str | None
    smtp_from_email: str | None
    smtp_from_name: str | None
    smtp_use_tls: bool
    has_password: bool
    updated_at: datetime | None
    updated_by_user_id: int | None


class SmtpUpdateRequest(BaseModel):
    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    smtp_username: str | None = Field(default=None, max_length=255)
    # `null` (omit) = keep current; "" = clear; anything else = set new value
    smtp_password: str | None = Field(default=None, max_length=512)
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = Field(default=None, max_length=255)
    smtp_use_tls: bool | None = None


class SmtpTestRequest(BaseModel):
    to: EmailStr
    # Optional: try with this candidate config instead of the saved one.
    # Useful to validate before saving.
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str | None = None
    smtp_use_tls: bool | None = None


class SmtpTestResponse(BaseModel):
    ok: bool
    detail: str


@router.get("/smtp", response_model=SmtpReadResponse)
async def get_smtp(db: DbSession, _: AdminUser):
    row = await settings_service.get_settings_row(db)
    return SmtpReadResponse(
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        smtp_from_email=row.smtp_from_email,
        smtp_from_name=row.smtp_from_name,
        smtp_use_tls=row.smtp_use_tls,
        has_password=row.smtp_password_encrypted is not None,
        updated_at=row.updated_at,
        updated_by_user_id=row.updated_by_user_id,
    )


@router.patch("/smtp", response_model=SmtpReadResponse)
async def update_smtp(
    payload: SmtpUpdateRequest, request: Request, db: DbSession, actor: AdminUser
):
    row = await settings_service.update_smtp_settings(
        db,
        actor_id=actor.id,
        host=payload.smtp_host,
        port=payload.smtp_port,
        username=payload.smtp_username,
        password=payload.smtp_password,
        from_email=str(payload.smtp_from_email) if payload.smtp_from_email else None,
        from_name=payload.smtp_from_name,
        use_tls=payload.smtp_use_tls,
    )
    await audit.record(
        db,
        action="smtp_settings_updated",
        entity="app_settings",
        entity_id=1,
        user_id=actor.id,
        # The password ciphertext is irrelevant to the audit trail; only log
        # which fields changed (presence/absence).
        after={
            "host": row.smtp_host,
            "port": row.smtp_port,
            "from_email": row.smtp_from_email,
            "use_tls": row.smtp_use_tls,
            "has_password": row.smtp_password_encrypted is not None,
        },
        **get_request_metadata(request),
    )
    return SmtpReadResponse(
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        smtp_from_email=row.smtp_from_email,
        smtp_from_name=row.smtp_from_name,
        smtp_use_tls=row.smtp_use_tls,
        has_password=row.smtp_password_encrypted is not None,
        updated_at=row.updated_at,
        updated_by_user_id=row.updated_by_user_id,
    )


@router.post("/smtp/test", response_model=SmtpTestResponse)
async def test_smtp(payload: SmtpTestRequest, db: DbSession, _: AdminUser):
    """Send a test email. If candidate fields are provided, use them; else
    use the stored config. Returns a clean success/failure result without
    raising — easier for the UI to display the error verbatim."""
    if any(
        getattr(payload, f) is not None
        for f in ("smtp_host", "smtp_port", "smtp_username", "smtp_password",
                  "smtp_from_email", "smtp_from_name", "smtp_use_tls")
    ):
        # Use the candidate (don't persist)
        if not payload.smtp_host or not payload.smtp_from_email:
            return SmtpTestResponse(
                ok=False, detail="Falta smtp_host o smtp_from_email"
            )
        override = SmtpConfig(
            host=payload.smtp_host,
            port=payload.smtp_port or 587,
            username=payload.smtp_username,
            password=payload.smtp_password,
            from_email=str(payload.smtp_from_email),
            from_name=payload.smtp_from_name or "Arxiu de notes",
            use_tls=payload.smtp_use_tls if payload.smtp_use_tls is not None else True,
        )
    else:
        override = None

    try:
        await _send_message(
            session=db if override is None else None,
            to=str(payload.to),
            subject="Arxiu de notes — prova de configuració SMTP",
            plain_body=(
                "Si reps aquest correu, la configuració SMTP de l'Arxiu de notes "
                "funciona correctament.\n\n— Arxiu Institut la Ferreria"
            ),
            smtp_override=override,
        )
        return SmtpTestResponse(ok=True, detail=f"Email enviat a {payload.to}")
    except Exception as exc:
        return SmtpTestResponse(ok=False, detail=str(exc)[:500])
