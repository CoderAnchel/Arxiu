"""Admin user management — create, regenerate password, email password, bulk."""
from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.v1.deps import AdminUser, DbSession, get_request_metadata
from app.core.exceptions import ArxiuError
from app.schemas.user import (
    BulkPasswordRequest,
    BulkPasswordResponse,
    BulkPasswordRow,
    PasswordRegenerateResponse,
    UserCreate,
    UserCreateResponse,
    UserResponse,
    UserUpdate,
)
from app.services import users as user_service
from app.services.email import send_password_email

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _to_response(user) -> UserResponse:  # type: ignore[no-untyped-def]
    return UserResponse(
        id=user.id,
        dni=user.dni,
        email=user.email,
        nom=user.nom,
        cognoms=user.cognoms,
        departament=user.departament,
        role=user.role,
        active=user.active,
        must_change_password=user.must_change_password,
        has_oauth_linked=bool(user.oauth_subject),
        has_mfa=bool(user.mfa_secret),
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
@router.get("", response_model=list[UserResponse])
async def list_users(
    db: DbSession,
    _: AdminUser,
) -> list[UserResponse]:
    users = await user_service.list_users(db)
    return [_to_response(u) for u in users]


# ---------------------------------------------------------------------------
@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> UserCreateResponse:
    meta = get_request_metadata(request)
    try:
        user, plaintext = await user_service.create_user(
            db, payload=payload, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    base = _to_response(user)
    return UserCreateResponse(**base.model_dump(), generated_password=plaintext)


# ---------------------------------------------------------------------------
@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> UserResponse:
    meta = get_request_metadata(request)
    try:
        user = await user_service.update_user(
            db, user_id=user_id, payload=payload, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
    return _to_response(user)


# ---------------------------------------------------------------------------
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def soft_delete_user(
    user_id: int,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> None:
    meta = get_request_metadata(request)
    try:
        await user_service.soft_delete_user(
            db, user_id=user_id, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc


# ---------------------------------------------------------------------------
@router.post("/{user_id}/regenerate-password", response_model=PasswordRegenerateResponse)
async def regenerate_password(
    user_id: int,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> PasswordRegenerateResponse:
    meta = get_request_metadata(request)
    try:
        _user, plaintext = await user_service.regenerate_password(
            db, user_id=user_id, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc
    return PasswordRegenerateResponse(user_id=user_id, generated_password=plaintext)


# ---------------------------------------------------------------------------
@router.post(
    "/{user_id}/email-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def email_password(
    user_id: int,
    db: DbSession,
    _actor: AdminUser,
) -> None:
    """Email the most recently generated password (within reveal TTL) to the user.
    The plaintext is consumed from Redis — this endpoint can only be called once
    per generate/regenerate cycle.
    """
    plaintext = await user_service.fetch_password_reveal(user_id)
    if plaintext is None:
        raise HTTPException(status.HTTP_410_GONE, "reveal_window_expired")
    user = await user_service.get_user(db, user_id)
    await send_password_email(
        session=db, to=user.email, name=f"{user.nom} {user.cognoms}",
        dni=user.dni, password=plaintext,
    )


# ---------------------------------------------------------------------------
@router.post("/bulk-generate-passwords")
async def bulk_generate_passwords(
    payload: BulkPasswordRequest,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> StreamingResponse:
    """Bulk regenerate. Returns a CSV download with the new credentials."""
    meta = get_request_metadata(request)
    try:
        results = await user_service.bulk_regenerate_passwords(
            db, user_ids=payload.user_ids, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    rows = [
        BulkPasswordRow(
            user_id=u.id,
            dni=u.dni,
            email=u.email,
            nom=u.nom,
            cognoms=u.cognoms,
            generated_password=p,
        )
        for u, p in results
    ]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["user_id", "dni", "email", "nom", "cognoms", "generated_password"])
    for r in rows:
        writer.writerow([r.user_id, r.dni, r.email, r.nom, r.cognoms, r.generated_password])
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="arxiu-credencials.csv"'},
    )


# Also expose JSON variant for tests / programmatic clients
@router.post("/bulk-generate-passwords/json", response_model=BulkPasswordResponse)
async def bulk_generate_passwords_json(
    payload: BulkPasswordRequest,
    request: Request,
    db: DbSession,
    actor: AdminUser,
) -> BulkPasswordResponse:
    meta = get_request_metadata(request)
    try:
        results = await user_service.bulk_regenerate_passwords(
            db, user_ids=payload.user_ids, actor_id=actor.id, **meta
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    return BulkPasswordResponse(
        rows=[
            BulkPasswordRow(
                user_id=u.id,
                dni=u.dni,
                email=u.email,
                nom=u.nom,
                cognoms=u.cognoms,
                generated_password=p,
            )
            for u, p in results
        ]
    )
