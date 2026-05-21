"""Structural invariants enforced everywhere:
- assignacions_docents: grup.curs must equal modul.curs
- qualificacions_ra (batch): matrícula.curs must equal modul.curs
- qualificacions_modul (manual override): same rule
- grade matrix never lists alumnes whose curs ≠ modul.curs
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.factories import make_admin


pytestmark = pytest.mark.asyncio


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "00000000T", "password": "Admin-Pwd-1!"},
    )
    return r.json()["access_token"]


async def _make_dam1a_with_m6(client: AsyncClient, h: dict) -> dict:
    curs = (
        await client.post("/api/v1/cursos-academics", headers=h, json={"nom": "2025-2026", "actiu": True})
    ).json()
    cicle = (
        await client.post(
            "/api/v1/cicles",
            headers=h,
            json={"codi": "DAM", "nom": "DAM", "nivell": "superior", "durada": 2},
        )
    ).json()
    m3 = (
        await client.post(
            "/api/v1/moduls",
            headers=h,
            json={"cicle_id": cicle["id"], "codi": "M03", "nom": "Programació", "curs": 1, "hores": 264},
        )
    ).json()
    m6 = (
        await client.post(
            "/api/v1/moduls",
            headers=h,
            json={"cicle_id": cicle["id"], "codi": "M06", "nom": "Accés a dades", "curs": 2, "hores": 165},
        )
    ).json()
    grup = (
        await client.post(
            "/api/v1/grups",
            headers=h,
            json={"codi": "DAM1A", "curs_acad_id": curs["id"], "cicle_id": cicle["id"], "curs": 1},
        )
    ).json()
    return {"curs": curs, "cicle": cicle, "m3": m3, "m6": m6, "grup": grup}


async def test_assignacio_rejects_modul_with_different_curs(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _make_dam1a_with_m6(client, h)

    # Need a docent
    docent = (
        await client.post(
            "/api/v1/admin/users",
            headers=h,
            json={
                "dni": "11111111A",
                "email": "p@inslaferreria.cat",
                "role": "professor",
                "nom": "P",
                "cognoms": "Q",
            },
        )
    ).json()

    r = await client.post(
        "/api/v1/assignacions-docents",
        headers=h,
        json={
            "user_id": docent["id"],
            "grup_id": ctx["grup"]["id"],
            "modul_id": ctx["m6"]["id"],  # 2n curs
            "curs_acad_id": ctx["curs"]["id"],
        },
    )
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"
    # Same modul on the matching curs works
    r2 = await client.post(
        "/api/v1/assignacions-docents",
        headers=h,
        json={
            "user_id": docent["id"],
            "grup_id": ctx["grup"]["id"],
            "modul_id": ctx["m3"]["id"],
            "curs_acad_id": ctx["curs"]["id"],
        },
    )
    assert r2.status_code == 201


async def test_grade_matrix_hides_curs_mismatched_matricules(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _make_dam1a_with_m6(client, h)

    # Add RA + matricula + avaluació
    await client.post(
        "/api/v1/ras",
        headers=h,
        json={"modul_id": ctx["m6"]["id"], "ordre": 1, "codi": "RA1", "descripcio": "x", "pes": 100},
    )
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    await client.post(
        "/api/v1/matricules",
        headers=h,
        json={
            "alumne_id": al["id"],
            "grup_id": ctx["grup"]["id"],
            "cicle_id": ctx["cicle"]["id"],
            "curs": 1,
            "curs_acad_id": ctx["curs"]["id"],
        },
    )
    aval = (
        await client.post(
            "/api/v1/avaluacions",
            headers=h,
            json={"curs_acad_id": ctx["curs"]["id"], "nom": "1a", "ordre": 1},
        )
    ).json()

    r = await client.get(
        "/api/v1/qualificacions/ra",
        headers=h,
        params={
            "grup_id": ctx["grup"]["id"],
            "modul_id": ctx["m6"]["id"],  # 2n curs
            "avaluacio_id": aval["id"],
        },
    )
    assert r.status_code == 200
    assert r.json()["alumnes"] == []  # curs mismatch → hidden


async def test_modul_batch_rejects_curs_mismatch(client: AsyncClient, db) -> None:
    """The manual final-note endpoint should refuse curs mismatched rows."""
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _make_dam1a_with_m6(client, h)

    # Need an avaluació and a matrícula on 1r curs
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    matr = (
        await client.post(
            "/api/v1/matricules",
            headers=h,
            json={
                "alumne_id": al["id"],
                "grup_id": ctx["grup"]["id"],
                "cicle_id": ctx["cicle"]["id"],
                "curs": 1,
                "curs_acad_id": ctx["curs"]["id"],
            },
        )
    ).json()
    aval = (
        await client.post(
            "/api/v1/avaluacions",
            headers=h,
            json={"curs_acad_id": ctx["curs"]["id"], "nom": "1a", "ordre": 1},
        )
    ).json()
    # Advance to docent so admin can edit; admin always can though
    for tgt in ("docent",):
        await client.post(f"/api/v1/avaluacions/{aval['id']}/transition", headers=h, json={"target": tgt})

    r = await client.patch(
        "/api/v1/qualificacions/modul/batch",
        headers=h,
        json={
            "avaluacio_id": aval["id"],
            "modul_id": ctx["m6"]["id"],
            "patches": [{"matricula_id": matr["id"], "nota": 7}],
        },
    )
    assert r.status_code == 200  # batch endpoint returns 200 with per-row results
    body = r.json()
    assert body["saved"] == 0
    assert body["failed"] == 1
    assert body["results"][0]["error"] == "curs_mismatch"


async def test_ra_batch_persists_comentari(client: AsyncClient, db) -> None:
    """Comentari per RA round-trips through the batch endpoint."""
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _make_dam1a_with_m6(client, h)

    ra = (
        await client.post(
            "/api/v1/ras",
            headers=h,
            json={"modul_id": ctx["m3"]["id"], "ordre": 1, "codi": "RA1", "descripcio": "x", "pes": 100},
        )
    ).json()
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    matr = (
        await client.post(
            "/api/v1/matricules",
            headers=h,
            json={
                "alumne_id": al["id"],
                "grup_id": ctx["grup"]["id"],
                "cicle_id": ctx["cicle"]["id"],
                "curs": 1,
                "curs_acad_id": ctx["curs"]["id"],
            },
        )
    ).json()
    aval = (
        await client.post(
            "/api/v1/avaluacions",
            headers=h,
            json={"curs_acad_id": ctx["curs"]["id"], "nom": "1a", "ordre": 1},
        )
    ).json()

    r = await client.patch(
        "/api/v1/qualificacions/ra/batch",
        headers=h,
        json={
            "avaluacio_id": aval["id"],
            "patches": [
                {
                    "matricula_id": matr["id"],
                    "ra_id": ra["id"],
                    "nota": 7,
                    "comentari": "Lliurament a temps però amb errors menors",
                }
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["saved"] == 1

    # Read back through the matrix
    g = await client.get(
        "/api/v1/qualificacions/ra",
        headers=h,
        params={
            "grup_id": ctx["grup"]["id"],
            "modul_id": ctx["m3"]["id"],
            "avaluacio_id": aval["id"],
        },
    )
    assert g.status_code == 200
    cells = g.json()["cells"]
    assert len(cells) == 1
    assert cells[0]["comentari"] == "Lliurament a temps però amb errors menors"


async def test_modul_manual_override_appears_in_matrix(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _make_dam1a_with_m6(client, h)
    al = (
        await client.post(
            "/api/v1/alumnes",
            headers=h,
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
        )
    ).json()
    matr = (
        await client.post(
            "/api/v1/matricules",
            headers=h,
            json={
                "alumne_id": al["id"],
                "grup_id": ctx["grup"]["id"],
                "cicle_id": ctx["cicle"]["id"],
                "curs": 1,
                "curs_acad_id": ctx["curs"]["id"],
            },
        )
    ).json()
    aval = (
        await client.post(
            "/api/v1/avaluacions",
            headers=h,
            json={"curs_acad_id": ctx["curs"]["id"], "nom": "1a", "ordre": 1},
        )
    ).json()

    # Manual override
    r = await client.patch(
        "/api/v1/qualificacions/modul/batch",
        headers=h,
        json={
            "avaluacio_id": aval["id"],
            "modul_id": ctx["m3"]["id"],
            "patches": [{"matricula_id": matr["id"], "nota": 8.5, "comentari": "manual"}],
        },
    )
    assert r.status_code == 200
    assert r.json()["saved"] == 1

    g = await client.get(
        "/api/v1/qualificacions/ra",
        headers=h,
        params={
            "grup_id": ctx["grup"]["id"],
            "modul_id": ctx["m3"]["id"],
            "avaluacio_id": aval["id"],
        },
    )
    mcs = g.json()["modul_cells"]
    assert len(mcs) == 1
    assert mcs[0]["nota"] == 8.5
    assert mcs[0]["comentari"] == "manual"
