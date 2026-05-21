"""Auth endpoints — login, refresh, logout, change-password, /me."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.api.v1.deps import (
    CurrentUser,
    DbSession,
    bearer_scheme,
    get_current_user_password_change_scope,
    get_request_metadata,
)
from app.core.config import get_settings
from app.core.exceptions import (
    AccountInactive,
    ArxiuError,
    InvalidCredentials,
    InvalidToken,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.models.people import AssignacioDocent, GrupClasse
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshResponse,
)
from app.services import auth as auth_service


class AssignacioRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grup_id: int
    modul_id: int
    curs_acad_id: int
    grup_codi: str | None = None
    is_tutor: bool = False


class MyAssignacionsResponse(BaseModel):
    role: str
    assignacions: list[AssignacioRow]
    tutorships: list[int]

router = APIRouter(prefix="/auth", tags=["auth"])

_REFRESH_COOKIE = "arxiu_refresh"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        max_age=settings.jwt_refresh_ttl_seconds,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth")


# ---------------------------------------------------------------------------
@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> LoginResponse:
    meta = get_request_metadata(request)
    try:
        user = await auth_service.authenticate(
            db,
            identifier=payload.identifier,
            password=payload.password,
            totp_code=payload.totp_code,
            ip=meta["ip"],
            user_agent=meta["user_agent"],
        )
    except InvalidCredentials as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.code) from exc
    except AccountInactive as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, exc.code) from exc

    access, pw_change, refresh, expires_in = await auth_service.issue_login_tokens(user)

    if refresh:
        _set_refresh_cookie(response, refresh)

    return LoginResponse(
        access_token=access,
        password_change_token=pw_change,
        must_change_password=user.must_change_password,
        expires_in=expires_in,
        role=user.role,
        user_id=user.id,
    )


# ---------------------------------------------------------------------------
@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> RefreshResponse:
    if not refresh_cookie:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_refresh_token")
    try:
        access, new_refresh, expires_in = await auth_service.refresh_access_token(refresh_cookie)
    except InvalidToken as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, exc.code) from exc

    _set_refresh_cookie(response, new_refresh)
    return RefreshResponse(access_token=access, expires_in=expires_in)


# ---------------------------------------------------------------------------
@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def logout(
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=_REFRESH_COOKIE)] = None,
) -> None:
    if refresh_cookie:
        await auth_service.revoke_refresh(refresh_cookie)
    _clear_refresh_cookie(response)


# ---------------------------------------------------------------------------
@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    db: DbSession,
    # Accept either normal access token or password-change-scoped token.
    user: Annotated[User, Depends(get_current_user_password_change_scope)],
) -> None:
    meta = get_request_metadata(request)
    try:
        await auth_service.change_password(
            db,
            user=user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            ip=meta["ip"],
            user_agent=meta["user_agent"],
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    # After a successful change, issue a fresh access+refresh pair so the client
    # can transition out of the password-change scope without a second login.
    access, _, refresh_token, _ = await auth_service.issue_login_tokens(user)
    if refresh_token:
        _set_refresh_cookie(response, refresh_token)
    if access is not None:
        # Hint the client to upgrade its access token. Body kept empty to honour 204.
        response.headers["X-New-Access-Token"] = access


# ---------------------------------------------------------------------------
@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=user.id,
        dni=user.dni,
        email=user.email,
        nom=user.nom,
        cognoms=user.cognoms,
        departament=user.departament,
        role=user.role,
        active=user.active,
        must_change_password=user.must_change_password,
        has_mfa=bool(user.mfa_secret),
        has_oauth_linked=bool(user.oauth_subject),
    )


# ---------------------------------------------------------------------------
@router.get("/me/assignacions", response_model=MyAssignacionsResponse)
async def my_assignacions(user: CurrentUser, db: DbSession) -> MyAssignacionsResponse:
    """Returns the (grup, mòdul) combinations the current user is assigned to,
    plus the grup ids where they are tutor. Admin gets empty arrays (admin can
    access everything; the frontend doesn't need to restrict the selectors)."""
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    if role_value == "admin":
        return MyAssignacionsResponse(role="admin", assignacions=[], tutorships=[])

    tutorships = list(
        (
            await db.execute(
                select(GrupClasse.id).where(
                    GrupClasse.tutor_user_id == user.id,
                    GrupClasse.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    tutorships_set = set(tutorships)

    rows_raw = list(
        (
            await db.execute(
                select(AssignacioDocent, GrupClasse.codi)
                .join(GrupClasse, GrupClasse.id == AssignacioDocent.grup_id)
                .where(
                    AssignacioDocent.user_id == user.id,
                    AssignacioDocent.deleted_at.is_(None),
                )
            )
        ).all()
    )

    rows: list[AssignacioRow] = [
        AssignacioRow(
            grup_id=assig.grup_id,
            modul_id=assig.modul_id,
            curs_acad_id=assig.curs_acad_id,
            grup_codi=grup_codi,
            is_tutor=assig.grup_id in tutorships_set,
        )
        for assig, grup_codi in rows_raw
    ]

    return MyAssignacionsResponse(role=role_value, assignacions=rows, tutorships=tutorships)


# Make sure the bearer scheme is referenced so OpenAPI documents it.
_ = bearer_scheme
