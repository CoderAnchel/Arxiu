"""Dashboard summary + tree endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.factories import make_admin


pytestmark = pytest.mark.asyncio


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


async def test_dashboard_empty_state_returns_zeros(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    r = await client.get(
        "/api/v1/dashboard", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["alumnes_matriculats"] == 0
    assert body["recent_activity"] != []  # at least the admin login event


async def test_dashboard_tree_groups_cicles(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    curs = (
        await client.post(
            "/api/v1/cursos-academics", headers=h, json={"nom": "2025-2026", "actiu": True}
        )
    ).json()
    cicle = (
        await client.post(
            "/api/v1/cicles",
            headers=h,
            json={"codi": "DAM", "nom": "DAM", "nivell": "superior", "durada": 2},
        )
    ).json()
    await client.post(
        "/api/v1/grups",
        headers=h,
        json={
            "codi": "DAM1A",
            "curs_acad_id": curs["id"],
            "cicle_id": cicle["id"],
            "curs": 1,
        },
    )

    r = await client.get(
        "/api/v1/dashboard/tree", headers=h, params={"curs_acad_id": curs["id"]}
    )
    assert r.status_code == 200
    tree = r.json()
    assert len(tree) == 1
    assert tree[0]["codi"] == "DAM"
    assert tree[0]["grups"][0]["codi"] == "DAM1A"
