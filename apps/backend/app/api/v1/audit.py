"""Audit log viewer (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.v1.deps import AdminUser, DbSession
from app.models.audit_log import AuditLog
from app.schemas.imports import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_logs(
    db: DbSession,
    _: AdminUser,
    user_id: int | None = Query(default=None),
    entity: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.limit(limit).offset(offset)

    rows = list((await db.execute(stmt)).scalars().all())
    return [
        AuditLogResponse(
            id=r.id,
            user_id=r.user_id,
            action=r.action,
            entity=r.entity,
            entity_id=r.entity_id,
            before=r.before_state,
            after=r.after_state,
            ip=r.ip,
            user_agent=r.user_agent,
            created_at=r.created_at,
        )
        for r in rows
    ]
