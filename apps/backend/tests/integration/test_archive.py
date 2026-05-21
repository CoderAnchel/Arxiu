"""Tests for the archive endpoints — historical view of alumne + grup."""
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


async def _setup(client: AsyncClient, h: dict) -> dict:
    curs = (
        await client.post(
            "/api/v1/cursos-academics",
            headers=h,
            json={"nom": "2025-2026", "actiu": True},
        )
    ).json()
    cicle = (
        await client.post(
            "/api/v1/cicles",
            headers=h,
            json={"codi": "DAM", "nom": "DAM", "nivell": "superior", "durada": 2},
        )
    ).json()
    modul = (
        await client.post(
            "/api/v1/moduls",
            headers=h,
            json={
                "cicle_id": cicle["id"],
                "codi": "M03",
                "nom": "Programació",
                "curs": 1,
                "hores": 264,
            },
        )
    ).json()
    grup = (
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
    ).json()
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R0000001", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    await client.post(
        "/api/v1/matricules",
        headers=h,
        json={
            "alumne_id": al["id"],
            "grup_id": grup["id"],
            "cicle_id": cicle["id"],
            "curs": 1,
            "curs_acad_id": curs["id"],
        },
    )
    return {"alumne": al, "grup": grup, "modul": modul}


async def test_alumne_expedient_returns_matricules(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, h)

    r = await client.get(f"/api/v1/archive/alumne/{ctx['alumne']['id']}/expedient", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["alumne"]["id"] == ctx["alumne"]["id"]
    assert len(body["matricules"]) == 1
    matr = body["matricules"][0]
    assert matr["grup_codi"] == "DAM1A"
    assert any(m["modul_codi"] == "M03" for m in matr["moduls"])


async def test_grup_expedient_returns_alumnes(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, h)

    r = await client.get(f"/api/v1/archive/grup/{ctx['grup']['id']}/expedient", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["grup_codi"] == "DAM1A"
    assert len(body["alumnes"]) == 1


async def test_archive_search_returns_hits(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    await _setup(client, h)
    r = await client.get("/api/v1/archive/search", headers=h, params={"q": "R0000001"})
    assert r.status_code == 200
    hits = r.json()
    assert any(h["kind"] == "alumne" for h in hits)


async def test_alumne_expedient_404(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    r = await client.get("/api/v1/archive/alumne/99999/expedient", headers=h)
    assert r.status_code == 404
