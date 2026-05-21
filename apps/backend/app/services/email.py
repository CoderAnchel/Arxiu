"""Email service: low-level send + high-level helpers (credentials, butlleti).
SMTP via aiosmtplib; templates via Jinja2.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.message import EmailMessage

import aiosmtplib
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.enviaments import Enviament, EstatEnviament
from app.services.settings import SmtpConfig, get_smtp_config

logger = logging.getLogger(__name__)


async def _send_message(
    *,
    session: AsyncSession | None = None,
    to: str,
    subject: str,
    plain_body: str,
    html_body: str | None = None,
    attachment: tuple[str, bytes, str] | None = None,
    smtp_override: SmtpConfig | None = None,
) -> None:
    """Build an EmailMessage and send via SMTP. Raises on transport failure.

    SMTP config priority:
      1. `smtp_override` (used by the "test connection" endpoint)
      2. The DB row (set via UI by an admin)
      3. The env-var fallback (legacy / dev mode)
    """
    if smtp_override is not None:
        cfg = smtp_override
    elif session is not None:
        cfg = await get_smtp_config(session)
    else:
        env = get_settings()
        cfg = SmtpConfig(
            host=env.smtp_host or "",
            port=env.smtp_port or 587,
            username=env.smtp_user or None,
            password=env.smtp_password or None,
            from_email=env.smtp_from_address or "",
            from_name=env.smtp_from_name or "Arxiu",
            use_tls=bool(env.smtp_use_tls),
        )

    if not cfg.configured:
        raise RuntimeError(
            "SMTP no configurat. Demana a l'administrador d'omplir la "
            "configuració SMTP des de Administració → Email."
        )

    msg = EmailMessage()
    msg["From"] = f"{cfg.from_name} <{cfg.from_email}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(plain_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if attachment is not None:
        filename, payload, mime = attachment
        maintype, _, subtype = mime.partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        msg.add_attachment(payload, maintype=maintype, subtype=subtype, filename=filename)

    use_tls = cfg.use_tls and cfg.port == 465
    start_tls = cfg.use_tls and cfg.port != 465

    await aiosmtplib.send(
        msg,
        hostname=cfg.host,
        port=cfg.port,
        username=cfg.username,
        password=cfg.password,
        use_tls=use_tls,
        start_tls=start_tls,
    )


# ---------------------------------------------------------------------------
# Credentials email (used by admin password management)
# ---------------------------------------------------------------------------

async def send_password_email(
    *, session: AsyncSession | None = None, to: str, name: str, dni: str, password: str
) -> None:
    body = (
        f"Hola {name},\n\n"
        f"L'administrador t'ha generat una contrasenya inicial per accedir a l'Arxiu de notes "
        f"de l'Institut la Ferreria.\n\n"
        f"  DNI / NIE:    {dni}\n"
        f"  Contrasenya:  {password}\n\n"
        f"En el primer accés se't demanarà que la canviïs per una de pròpia.\n\n"
        f"Si no esperaves aquest correu, contacta amb la coordinació del centre.\n\n"
        f"— Arxiu Institut la Ferreria"
    )
    await _send_message(
        session=session,
        to=to,
        subject="Arxiu Institut la Ferreria — credencials d'accés",
        plain_body=body,
    )
    logger.info("password_email_sent", extra={"to": to, "dni": dni})


# ---------------------------------------------------------------------------
# Butlletí email
# ---------------------------------------------------------------------------

async def send_butlleti(
    *,
    session: AsyncSession | None = None,
    enviament: Enviament,
    pdf_bytes: bytes,
    plain_body: str,
    html_body: str,
) -> None:
    """Send a butlleti to a recipient. Mutates the Enviament with sent_at/error_msg
    but does NOT commit — caller controls the transaction.
    """
    try:
        await _send_message(
            session=session,
            to=enviament.destinatari_email,
            subject=enviament.assumpte,
            plain_body=plain_body,
            html_body=html_body,
            attachment=(enviament.adjunt_filename or "butlleti.pdf", pdf_bytes, "application/pdf"),
        )
        enviament.estat = EstatEnviament.ENVIAT
        enviament.sent_at = datetime.now(timezone.utc)
        enviament.error_msg = None
    except Exception as exc:  # pragma: no cover — exercised via integration tests with mocked SMTP
        msg = str(exc)[:480]
        is_bounce = any(
            kw in msg.lower() for kw in ("user unknown", "mailbox unavailable", "no such user", "rejected")
        )
        enviament.estat = EstatEnviament.REBOTAT if is_bounce else EstatEnviament.ERROR
        enviament.error_msg = msg
        logger.warning("butlleti_send_failed", extra={"to": enviament.destinatari_email, "err": msg})
