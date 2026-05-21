"""Runtime settings management.

The admin can edit SMTP credentials from the UI. To avoid plaintext on disk,
the SMTP password is encrypted with Fernet using a key derived from
`SETTINGS_ENCRYPTION_KEY` (env) — or, as a fallback, from the JWT private key
so we don't need a new secret in the bootstrap.

`get_smtp_config()` returns the runtime SMTP config: it prefers the DB row
(set via UI) and falls back to env-vars (set at deploy time) so the system
keeps working out of the box.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.app_settings import AppSettings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    """Return a Fernet instance using a key derived deterministically."""
    settings = get_settings()
    raw = getattr(settings, "settings_encryption_key", None)
    if not raw:
        # Derive a stable key from the JWT private key path content. Stable
        # across restarts as long as the keypair doesn't change.
        path = getattr(settings, "jwt_private_key_path", None)
        if path and Path(path).exists():
            raw = Path(path).read_bytes()
        else:
            raw = b"insecure-dev-fallback-do-not-use-in-prod"
    digest = hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_password(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_password(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        logger.warning("smtp_password_decrypt_failed")
        return None


# ----- Runtime accessors used by the email service -------------------------


@dataclass(frozen=True, slots=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str
    from_name: str
    use_tls: bool

    @property
    def configured(self) -> bool:
        return bool(self.host and self.from_email)


async def get_smtp_config(session: AsyncSession) -> SmtpConfig:
    """Read from DB; fall back to env settings if the DB row is empty."""
    env = get_settings()
    row = (await session.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()

    host = (row.smtp_host if row and row.smtp_host else env.smtp_host) or ""
    port = (row.smtp_port if row and row.smtp_port else env.smtp_port) or 587
    username = (row.smtp_username if row and row.smtp_username else env.smtp_user) or None
    if row and row.smtp_password_encrypted:
        password = decrypt_password(row.smtp_password_encrypted)
    else:
        password = env.smtp_password or None
    from_email = (
        (row.smtp_from_email if row and row.smtp_from_email else env.smtp_from_address) or ""
    )
    from_name = (
        (row.smtp_from_name if row and row.smtp_from_name else env.smtp_from_name) or "Arxiu de notes"
    )
    use_tls = row.smtp_use_tls if row is not None else env.smtp_use_tls

    return SmtpConfig(
        host=host,
        port=int(port),
        username=username,
        password=password,
        from_email=from_email,
        from_name=from_name,
        use_tls=bool(use_tls),
    )


# ----- Admin CRUD ----------------------------------------------------------


async def get_settings_row(session: AsyncSession) -> AppSettings:
    row = (await session.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()
    if row is None:
        row = AppSettings(id=1)
        session.add(row)
        await session.flush()
    return row


async def update_smtp_settings(
    session: AsyncSession,
    *,
    actor_id: int,
    host: str | None,
    port: int | None,
    username: str | None,
    password: str | None,  # plaintext; None = keep current; "" = clear
    from_email: str | None,
    from_name: str | None,
    use_tls: bool | None,
) -> AppSettings:
    row = await get_settings_row(session)
    if host is not None:
        row.smtp_host = host.strip() or None
    if port is not None:
        row.smtp_port = port
    if username is not None:
        row.smtp_username = username.strip() or None
    if password is not None:
        # "" means clear, anything else means re-encrypt
        row.smtp_password_encrypted = encrypt_password(password) if password else None
    if from_email is not None:
        row.smtp_from_email = from_email.strip() or None
    if from_name is not None:
        row.smtp_from_name = from_name.strip() or None
    if use_tls is not None:
        row.smtp_use_tls = use_tls
    row.updated_by_user_id = actor_id
    await session.flush()
    return row
