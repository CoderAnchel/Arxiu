"""End-to-end tests for the avaluacions state machine + grade matrix + bulk PATCH."""
from __future__ import annotations

from httpx import AsyncClient

from tests.factories import make_admin


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


async def _setup_basic_curriculum(client: AsyncClient, token: str) -> dict:
    """Create the minimum hierarchy needed for grading: curs + cicle + modul + ra + grup."""
    h = {"Authorization": f"Bearer {token}"}

    curs = await client.post(
        "/api/v1/cursos-academics", headers=h,
        json={"nom": "2025-2026", "actiu": True},
    )
    assert curs.status_code == 201

    cicle = await client.post(
        "/api/v1/cicles", headers=h,
        json={"codi": "DAM", "nom": "DAM", "nivell": "superior", "durada": 2},
    )
    assert cicle.status_code == 201

    modul = await client.post(
        "/api/v1/moduls", headers=h,
        json={"cicle_id": cicle.json()["id"], "codi": "M03",
              "nom": "Programació", "curs": 1, "hores": 264},
    )
    assert modul.status_code == 201

    ra = await client.post(
        "/api/v1/ras", headers=h,
        json={"modul_id": modul.json()["id"], "ordre": 1, "codi": "RA1",
              "descripcio": "Identifica…", "pes": 25},
    )
    assert ra.status_code == 201

    grup = await client.post(
        "/api/v1/grups", headers=h,
        json={"codi": "DAM1A", "curs_acad_id": curs.json()["id"],
              "cicle_id": cicle.json()["id"], "curs": 1},
    )
    assert grup.status_code == 201

    return {
        "curs_acad_id": curs.json()["id"],
        "cicle_id": cicle.json()["id"],
        "modul_id": modul.json()["id"],
        "ra_id": ra.json()["id"],
        "grup_id": grup.json()["id"],
    }


async def test_avaluacio_state_machine_forward_chain(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_basic_curriculum(client, token)

    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "1a Avaluació", "ordre": 1},
    )
    assert aval.status_code == 201
    assert aval.json()["estat"] == "oberta"

    aval_id = aval.json()["id"]

    for target in ("docent", "junta", "tancada"):
        r = await client.post(
            f"/api/v1/avaluacions/{aval_id}/transition", headers=h,
            json={"target": target},
        )
        assert r.status_code == 200, r.text
        assert r.json()["estat"] == target


async def test_skip_state_is_rejected(client: AsyncClient, db) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_basic_curriculum(client, token)
    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "Aval", "ordre": 1},
    )
    aval_id = aval.json()["id"]

    # oberta → junta is invalid (must go through docent)
    r = await client.post(
        f"/api/v1/avaluacions/{aval_id}/transition", headers=h, json={"target": "junta"}
    )
    assert r.status_code == 409


async def test_only_admin_can_transition(client: AsyncClient, db) -> None:
    from tests.factories import make_user

    admin_token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {admin_token}"}
    ctx = await _setup_basic_curriculum(client, admin_token)
    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "Aval", "ordre": 1},
    )
    aval_id = aval.json()["id"]

    await make_user(db, dni="55555555E", password="Prof-Pwd-1!")
    prof_login = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    prof_h = {"Authorization": f"Bearer {prof_login.json()['access_token']}"}

    r = await client.post(
        f"/api/v1/avaluacions/{aval_id}/transition", headers=prof_h, json={"target": "docent"}
    )
    assert r.status_code == 403


async def test_bulk_patch_admin_succeeds_in_any_state(client: AsyncClient, db) -> None:
    """Admin can edit notes regardless of avaluació state."""
    from app.models.people import Alumne, Matricula
    from sqlalchemy import select

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_basic_curriculum(client, token)

    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "Aval", "ordre": 1},
    )
    aval_id = aval.json()["id"]

    # Create alumne + matricula directly
    alumne = Alumne(ralc="0000000001", nom="Aleix", cognoms="Test")
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)
    matr = Matricula(
        alumne_id=alumne.id,
        grup_id=ctx["grup_id"],
        cicle_id=ctx["cicle_id"],
        curs=1,
        curs_acad_id=ctx["curs_acad_id"],
    )
    db.add(matr)
    await db.commit()
    await db.refresh(matr)

    # Initial state oberta — admin can still edit
    r = await client.patch(
        "/api/v1/qualificacions/ra/batch", headers=h,
        json={
            "avaluacio_id": aval_id,
            "patches": [
                {"matricula_id": matr.id, "ra_id": ctx["ra_id"], "nota": "7.5"},
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["saved"] == 1
    assert r.json()["failed"] == 0


async def test_bulk_patch_professor_blocked_without_assignacio(client: AsyncClient, db) -> None:
    from app.models.people import Alumne, Matricula
    from tests.factories import make_user

    admin_token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {admin_token}"}
    ctx = await _setup_basic_curriculum(client, admin_token)

    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "Aval", "ordre": 1},
    )
    aval_id = aval.json()["id"]
    # Move to docent so professor edit window is theoretically open
    await client.post(f"/api/v1/avaluacions/{aval_id}/transition", headers=h, json={"target": "docent"})

    alumne = Alumne(ralc="0000000002", nom="B", cognoms="Test")
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)
    matr = Matricula(
        alumne_id=alumne.id, grup_id=ctx["grup_id"], cicle_id=ctx["cicle_id"],
        curs=1, curs_acad_id=ctx["curs_acad_id"],
    )
    db.add(matr)
    await db.commit()
    await db.refresh(matr)

    await make_user(db, dni="55555555E", password="Prof-Pwd-1!")
    prof_login = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    prof_h = {"Authorization": f"Bearer {prof_login.json()['access_token']}"}

    r = await client.patch(
        "/api/v1/qualificacions/ra/batch", headers=prof_h,
        json={
            "avaluacio_id": aval_id,
            "patches": [
                {"matricula_id": matr.id, "ra_id": ctx["ra_id"], "nota": "8.0"},
            ],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] == 0
    assert body["failed"] == 1
    assert body["results"][0]["error"] == "permission_denied"


async def test_grade_matrix_returns_alumnes_and_ras(client: AsyncClient, db) -> None:
    from app.models.people import Alumne, Matricula

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_basic_curriculum(client, token)
    aval = await client.post(
        "/api/v1/avaluacions", headers=h,
        json={"curs_acad_id": ctx["curs_acad_id"], "nom": "Aval", "ordre": 1},
    )
    aval_id = aval.json()["id"]

    for i, name in enumerate(["Aleix", "Berta", "Marc"]):
        a = Alumne(ralc=f"00000000{i+1:02d}", nom=name, cognoms="Test")
        db.add(a)
        await db.commit()
        await db.refresh(a)
        m = Matricula(
            alumne_id=a.id, grup_id=ctx["grup_id"], cicle_id=ctx["cicle_id"],
            curs=1, curs_acad_id=ctx["curs_acad_id"],
        )
        db.add(m)
        await db.commit()

    r = await client.get(
        "/api/v1/qualificacions/ra", headers=h,
        params={"grup_id": ctx["grup_id"], "modul_id": ctx["modul_id"], "avaluacio_id": aval_id},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["alumnes"]) == 3
    assert len(body["ras"]) == 1
    assert body["can_edit"] is True
    assert body["avaluacio_estat"] == "oberta"
