"""Integration tests for /api/v1/admin/users endpoints."""
from __future__ import annotations

from httpx import AsyncClient

from app.models.user import UserRole
from tests.factories import make_admin, make_user


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


async def _professor_token(client: AsyncClient, db) -> str:
    await make_user(
        db,
        dni="55555555E",
        email="prof@inslaferreria.cat",
        password="Prof-Pwd-1!",
        role=UserRole.PROFESSOR,
    )
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    return r.json()["access_token"]


# --- create user ------------------------------------------------------------

async def test_admin_can_create_user_and_receive_password_once(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "dni": "12345678Z",
            "email": "new.prof@inslaferreria.cat",
            "nom": "Núria",
            "cognoms": "Bonet",
            "role": "professor",
            "departament": "Informàtica",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["dni"] == "12345678Z"
    assert body["role"] == "professor"
    assert body["must_change_password"] is True
    assert body["generated_password"]
    assert len(body["generated_password"]) >= 16


async def test_create_user_rejects_duplicate_dni(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    payload = {
        "dni": "12345678Z",
        "email": "a@inslaferreria.cat",
        "nom": "A",
        "cognoms": "B",
        "role": "professor",
    }
    first = await client.post("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert first.status_code == 201

    payload["email"] = "b@inslaferreria.cat"
    second = await client.post("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert second.status_code == 409


async def test_professor_cannot_create_user(client: AsyncClient, db) -> None:
    token = await _professor_token(client, db)
    r = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "dni": "11223344Q",
            "email": "x@inslaferreria.cat",
            "nom": "X",
            "cognoms": "Y",
            "role": "professor",
        },
    )
    assert r.status_code == 403


async def test_anonymous_cannot_create_user(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/admin/users",
        json={"dni": "11223344Q", "email": "x@x", "nom": "X", "cognoms": "Y", "role": "professor"},
    )
    assert r.status_code == 401


# --- list -------------------------------------------------------------------

async def test_admin_can_list_users(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    await make_user(db, dni="11111111Z", email="a@inslaferreria.cat")
    r = await client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 2  # admin + new user


# --- regenerate password ----------------------------------------------------

async def test_admin_can_regenerate_password(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    target = await make_user(db, dni="22222222B", password="Old-Pwd-1!", must_change_password=False)

    r = await client.post(
        f"/api/v1/admin/users/{target.id}/regenerate-password",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    new_pw = r.json()["generated_password"]
    assert new_pw

    # Old password must no longer work
    bad = await client.post("/api/v1/auth/login", json={"identifier": "22222222B", "password": "Old-Pwd-1!"})
    assert bad.status_code == 401

    # New password works, but must_change_password is now True
    good = await client.post("/api/v1/auth/login", json={"identifier": "22222222B", "password": new_pw})
    assert good.status_code == 200
    assert good.json()["must_change_password"] is True


# --- bulk regenerate (JSON) -------------------------------------------------

async def test_admin_can_bulk_regenerate(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    u1 = await make_user(db, dni="11111111A", email="u1@inslaferreria.cat")
    u2 = await make_user(db, dni="22222222B", email="u2@inslaferreria.cat")

    r = await client.post(
        "/api/v1/admin/users/bulk-generate-passwords/json",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_ids": [u1.id, u2.id]},
    )
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert {r["user_id"] for r in rows} == {u1.id, u2.id}
    assert all(len(row["generated_password"]) >= 16 for row in rows)


async def test_admin_bulk_regenerate_csv_variant(client: AsyncClient, db) -> None:
    """Same payload, different content type — CSV download for the UI."""
    token = await _admin_token(client, db)
    u1 = await make_user(db, dni="11111111A", email="u1@inslaferreria.cat")
    r = await client.post(
        "/api/v1/admin/users/bulk-generate-passwords",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_ids": [u1.id]},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "arxiu-credencials.csv" in r.headers["content-disposition"]
    # Header row + one data row
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("user_id,dni,email,nom,cognoms,generated_password")
    assert len(lines) == 2


# --- update / delete --------------------------------------------------------

async def test_admin_can_update_and_soft_delete(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    target = await make_user(db, dni="77777777G", email="t@inslaferreria.cat")

    upd = await client.patch(
        f"/api/v1/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"departament": "Sanitat"},
    )
    assert upd.status_code == 200
    assert upd.json()["departament"] == "Sanitat"

    rm = await client.delete(
        f"/api/v1/admin/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert rm.status_code == 204

    # Login should now fail (soft-deleted)
    bad = await client.post(
        "/api/v1/auth/login", json={"identifier": "77777777G", "password": "Initial-Password-1!"}
    )
    assert bad.status_code == 401


async def test_admin_cannot_delete_themselves(client: AsyncClient, db) -> None:
    admin = await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    token = login.json()["access_token"]
    r = await client.delete(
        f"/api/v1/admin/users/{admin.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 409
