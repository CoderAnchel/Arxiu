"""Smoke tests for catalog endpoints."""
from __future__ import annotations

from httpx import AsyncClient

from tests.factories import make_admin


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


async def test_admin_can_create_full_currriculum(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}

    fam = await client.post("/api/v1/families", headers=h,
                            json={"codi": "INF", "nom": "Informàtica"})
    assert fam.status_code == 201

    cicle = await client.post("/api/v1/cicles", headers=h, json={
        "codi": "DAM", "nom": "Desenvolupament d'Aplicacions Multiplataforma",
        "familia_id": fam.json()["id"], "nivell": "superior", "durada": 2,
    })
    assert cicle.status_code == 201

    modul = await client.post("/api/v1/moduls", headers=h, json={
        "cicle_id": cicle.json()["id"], "codi": "M03",
        "nom": "Programació", "curs": 1, "hores": 264,
    })
    assert modul.status_code == 201

    ra = await client.post("/api/v1/ras", headers=h, json={
        "modul_id": modul.json()["id"], "ordre": 1, "codi": "RA1",
        "descripcio": "Identifica els elements del llenguatge…",
        "pes": 25,
    })
    assert ra.status_code == 201

    # Detail endpoint should return cicle + nested moduls + RAs
    detail = await client.get(f"/api/v1/cicles/{cicle.json()['id']}", headers=h)
    assert detail.status_code == 200
    body = detail.json()
    assert body["codi"] == "DAM"
    assert len(body["moduls"]) == 1
    assert body["moduls"][0]["codi"] == "M03"
    assert len(body["moduls"][0]["ras"]) == 1


async def test_duplicate_cicle_returns_409(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    payload = {"codi": "DAM", "nom": "X", "nivell": "superior"}
    a = await client.post("/api/v1/cicles", headers=h, json=payload)
    assert a.status_code == 201
    b = await client.post("/api/v1/cicles", headers=h, json={**payload, "nom": "Y"})
    assert b.status_code == 409


async def test_only_admin_can_create_cicle(client: AsyncClient, db) -> None:
    from tests.factories import make_user

    await make_user(db, dni="55555555E", email="prof@inslaferreria.cat", password="Prof-Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    r = await client.post(
        "/api/v1/cicles", headers=h,
        json={"codi": "DAW", "nom": "X", "nivell": "superior"},
    )
    assert r.status_code == 403


async def test_curs_actiu_only_one(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    a = await client.post("/api/v1/cursos-academics", headers=h,
                          json={"nom": "2024-2025", "actiu": True})
    b = await client.post("/api/v1/cursos-academics", headers=h,
                          json={"nom": "2025-2026", "actiu": True})
    assert a.status_code == 201
    assert b.status_code == 201

    actiu = await client.get("/api/v1/cursos-academics/active", headers=h)
    assert actiu.status_code == 200
    assert actiu.json()["nom"] == "2025-2026"

    listed = await client.get("/api/v1/cursos-academics", headers=h)
    actius = [c for c in listed.json() if c["actiu"]]
    assert len(actius) == 1
