"""Soft-delete + paperera restore round-trip."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.factories import make_admin, make_user
from app.models.user import UserRole


pytestmark = pytest.mark.asyncio


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "00000000T", "password": "Admin-Pwd-1!"},
    )
    return r.json()["access_token"]


async def test_trash_lists_only_soft_deleted(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}

    # Create + soft-delete an alumne
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    await client.delete(f"/api/v1/alumnes/{al['id']}", headers=h)

    # Paperera should list it
    r = await client.get("/api/v1/trash", headers=h)
    assert r.status_code == 200
    items = r.json()["alumne"]
    assert any(i["id"] == al["id"] for i in items)
    assert items[0]["deleted_at"] is not None


async def test_trash_restore_makes_item_visible_again(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}

    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    await client.delete(f"/api/v1/alumnes/{al['id']}", headers=h)

    # Restore
    r = await client.post(f"/api/v1/trash/alumne/{al['id']}/restore", headers=h)
    assert r.status_code == 204

    # Listed again in normal endpoint
    r2 = await client.get("/api/v1/alumnes", headers=h)
    assert any(a["id"] == al["id"] for a in r2.json())


async def test_trash_restore_unknown_kind_returns_400(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/trash/unicorn/1/restore", headers=h)
    assert r.status_code == 400


async def test_trash_restore_404_when_not_found(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/trash/alumne/9999/restore", headers=h)
    assert r.status_code == 404


async def test_trash_restore_409_when_not_deleted(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    r = await client.post(f"/api/v1/trash/alumne/{al['id']}/restore", headers=h)
    assert r.status_code == 409


async def test_trash_requires_admin(client: AsyncClient, db) -> None:
    await make_user(
        db,
        dni="11111111A",
        email="p@inslaferreria.cat",
        role=UserRole.PROFESSOR,
        password="Prof-Pwd-1!",
    )
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "11111111A", "password": "Prof-Pwd-1!"},
    )
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r2 = await client.get("/api/v1/trash", headers=h)
    assert r2.status_code == 403
