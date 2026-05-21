"""Audit log writer — append-only. Never updates or deletes."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record(
    session: AsyncSession,
    *,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    user_id: int | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """Write a single audit row. Caller is responsible for the session commit."""
    row = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        before_state=before,
        after_state=after,
        ip=ip,
        user_agent=(user_agent or "")[:500] or None,
    )
    session.add(row)
    return row
