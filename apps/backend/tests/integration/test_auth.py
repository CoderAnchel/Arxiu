"""Integration tests for /api/v1/auth endpoints."""
from __future__ import annotations

from httpx import AsyncClient

from app.models.user import UserRole
from tests.factories import make_user


# --- /healthz ---------------------------------------------------------------
async def test_healthz_still_works(client: AsyncClient) -> None:
    r = await client.get("/healthz")
    assert r.status_code == 200


# --- POST /auth/login -------------------------------------------------------

async def test_login_with_dni_succeeds(client: AsyncClient, db) -> None:
    await make_user(db, dni="12345678Z", email="alice@inslaferreria.cat", password="Strong-Pass-1!")
    r = await client.post("/api/v1/auth/login", json={"identifier": "12345678Z", "password": "Strong-Pass-1!"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["password_change_token"] is None
    assert body["must_change_password"] is False
    assert body["role"] in {"professor", "admin"}


async def test_login_with_email_succeeds(client: AsyncClient, db) -> None:
    await make_user(db, dni="12345678Z", email="alice@inslaferreria.cat", password="Strong-Pass-1!")
    r = await client.post("/api/v1/auth/login", json={"identifier": "alice@inslaferreria.cat", "password": "Strong-Pass-1!"})
    assert r.status_code == 200
    assert r.json()["access_token"]


async def test_login_returns_password_change_token_when_required(client: AsyncClient, db) -> None:
    await make_user(db, dni="22222222B", password="Initial-Pwd-1!", must_change_password=True)
    r = await client.post("/api/v1/auth/login", json={"identifier": "22222222B", "password": "Initial-Pwd-1!"})
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] is None
    assert body["password_change_token"]
    assert body["must_change_password"] is True


async def test_login_rejects_wrong_password(client: AsyncClient, db) -> None:
    await make_user(db, dni="33333333C", password="Real-Pwd-1!")
    r = await client.post("/api/v1/auth/login", json={"identifier": "33333333C", "password": "Wrong"})
    assert r.status_code == 401
    assert r.json()["error"] == "invalid_credentials"


async def test_login_rejects_unknown_user(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/login", json={"identifier": "99999999X", "password": "anything"})
    assert r.status_code == 401


async def test_login_rejects_inactive_user(client: AsyncClient, db) -> None:
    await make_user(db, dni="44444444D", password="Pwd-1!", active=False)
    r = await client.post("/api/v1/auth/login", json={"identifier": "44444444D", "password": "Pwd-1!"})
    assert r.status_code == 403
    assert r.json()["error"] == "account_inactive"


async def test_login_sets_refresh_cookie(client: AsyncClient, db) -> None:
    await make_user(db, dni="55555555E", password="Pwd-1!")
    r = await client.post("/api/v1/auth/login", json={"identifier": "55555555E", "password": "Pwd-1!"})
    assert "set-cookie" in {k.lower() for k in r.headers.keys()}
    assert any("arxiu_refresh" in v for v in r.headers.values())


async def test_login_no_refresh_cookie_when_password_change_required(client: AsyncClient, db) -> None:
    await make_user(db, dni="66666666F", password="Pwd-1!", must_change_password=True)
    r = await client.post("/api/v1/auth/login", json={"identifier": "66666666F", "password": "Pwd-1!"})
    cookies = " ".join(v for k, v in r.headers.items() if k.lower() == "set-cookie")
    assert "arxiu_refresh" not in cookies


# --- /auth/me ---------------------------------------------------------------

async def test_me_with_valid_token(client: AsyncClient, db) -> None:
    await make_user(db, dni="77777777G", password="Pwd-1!", role=UserRole.PROFESSOR)
    login = await client.post("/api/v1/auth/login", json={"identifier": "77777777G", "password": "Pwd-1!"})
    token = login.json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["dni"] == "77777777G"
    assert r.json()["role"] == "professor"


async def test_me_rejects_missing_token(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


# --- /auth/change-password --------------------------------------------------

async def test_change_password_flow_with_must_change(client: AsyncClient, db) -> None:
    await make_user(db, dni="88888888H", password="Initial-Pwd-1!", must_change_password=True)
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "88888888H", "password": "Initial-Pwd-1!"}
    )
    token = login.json()["password_change_token"]
    assert token

    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Initial-Pwd-1!", "new_password": "Brand-New-Pwd-2025!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 204, r.text

    # Now the user should be able to log in with the new password and get a normal token
    relog = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "88888888H", "password": "Brand-New-Pwd-2025!"},
    )
    assert relog.status_code == 200
    assert relog.json()["must_change_password"] is False
    assert relog.json()["access_token"]


async def test_change_password_rejects_bad_current(client: AsyncClient, db) -> None:
    await make_user(db, dni="99999999J", password="Real-Pwd-1!", must_change_password=False)
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "99999999J", "password": "Real-Pwd-1!"}
    )
    token = login.json()["access_token"]

    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Wrong", "new_password": "New-Strong-Pwd-1!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


async def test_change_password_enforces_min_length(client: AsyncClient, db) -> None:
    await make_user(db, dni="10101010K", password="Real-Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "10101010K", "password": "Real-Pwd-1!"}
    )
    token = login.json()["access_token"]
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Real-Pwd-1!", "new_password": "tooshort"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422


# --- /auth/refresh + /auth/logout ------------------------------------------

async def test_refresh_rotates_token(client: AsyncClient, db) -> None:
    await make_user(db, dni="20202020L", password="Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "20202020L", "password": "Pwd-1!"}
    )
    assert login.status_code == 200
    refresh_cookie = login.cookies.get("arxiu_refresh")
    assert refresh_cookie

    r = await client.post("/api/v1/auth/refresh", cookies={"arxiu_refresh": refresh_cookie})
    assert r.status_code == 200
    assert r.json()["access_token"]
    assert r.cookies.get("arxiu_refresh") != refresh_cookie  # rotated


async def test_refresh_reuse_revokes_family(client: AsyncClient, db) -> None:
    await make_user(db, dni="30303030M", password="Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "30303030M", "password": "Pwd-1!"}
    )
    refresh = login.cookies.get("arxiu_refresh")
    # First use rotates successfully
    first = await client.post("/api/v1/auth/refresh", cookies={"arxiu_refresh": refresh})
    assert first.status_code == 200
    # Replay of original cookie must fail (family revoked)
    second = await client.post("/api/v1/auth/refresh", cookies={"arxiu_refresh": refresh})
    assert second.status_code == 401


async def test_logout_clears_cookie_and_revokes(client: AsyncClient, db) -> None:
    await make_user(db, dni="40404040N", password="Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "40404040N", "password": "Pwd-1!"}
    )
    refresh = login.cookies.get("arxiu_refresh")
    r = await client.post("/api/v1/auth/logout", cookies={"arxiu_refresh": refresh})
    assert r.status_code == 204
    # Subsequent refresh must fail
    r2 = await client.post("/api/v1/auth/refresh", cookies={"arxiu_refresh": refresh})
    assert r2.status_code == 401


async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401
