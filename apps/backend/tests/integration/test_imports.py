"""Phase-5 imports tests — alumnes Excel/CSV import + confirm."""
from __future__ import annotations

import csv
import io

import pytest
from httpx import AsyncClient

from tests.factories import make_admin


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


def _make_csv(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")


@pytest.fixture
def storage_root(tmp_path, monkeypatch):
    """Redirect uploads into a tmp dir so tests don't pollute a shared volume."""
    from app.core.config import get_settings

    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
    get_settings.cache_clear()  # type: ignore[attr-defined]
    yield tmp_path
    get_settings.cache_clear()  # type: ignore[attr-defined]


async def test_alumnes_csv_preview_then_confirm(client: AsyncClient, db, storage_root) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}

    csv_bytes = _make_csv(
        [
            ["RALC", "DNI", "Nom", "Cognoms", "Email", "Email tutor"],
            ["1001", "12345678Z", "Aleix", "Vilanova", "aleix@example.cat", "tutor1@example.cat"],
            ["1002", "98765432X", "Berta", "Puigdomènech", "berta@example.cat", ""],
            ["1003", "", "Marc", "Riera", "marc@example.cat", ""],
        ]
    )

    files = {"file": ("alumnes.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/imports/alumnes", headers=h, files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["tipus"] == "alumnes"
    assert body["total"] == 3
    assert body["ok"] == 3
    assert body["errors"] == 0
    assert len(body["preview"]) == 3
    import_id = body["id"]

    # Confirm
    r2 = await client.post(f"/api/v1/imports/{import_id}/confirm", headers=h)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["estat"] == "completed"
    assert body2["result"]["created"] == 3
    assert body2["result"]["updated"] == 0
    assert body2["result"]["errors"] == 0

    # Listing alumnes shows the imports
    al = await client.get("/api/v1/alumnes?q=Aleix", headers=h)
    assert al.status_code == 200
    assert any(a["nom"] == "Aleix" for a in al.json())


async def test_alumnes_import_detects_missing_required_column(
    client: AsyncClient, db, storage_root
) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    # No RALC column
    csv_bytes = _make_csv([["DNI", "Nom", "Cognoms"], ["12345678Z", "A", "B"]])
    files = {"file": ("bad.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/imports/alumnes", headers=h, files=files)
    assert r.status_code == 422
    assert r.json()["detail"] == "validation_error"


async def test_alumnes_import_flags_invalid_email_per_row(
    client: AsyncClient, db, storage_root
) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    csv_bytes = _make_csv(
        [
            ["RALC", "Nom", "Cognoms", "Email"],
            ["2001", "OK", "Person", "ok@example.cat"],
            ["2002", "Bad", "Email", "not-an-email"],
        ]
    )
    files = {"file": ("alumnes.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/imports/alumnes", headers=h, files=files)
    assert r.status_code == 201
    body = r.json()
    assert body["ok"] == 1
    assert body["errors"] == 1
    bad_row = next(p for p in body["preview"] if p["data"]["ralc"] == "2002")
    assert any("email" in e for e in bad_row["errors"])


async def test_alumnes_import_dedupes_within_file(
    client: AsyncClient, db, storage_root
) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    csv_bytes = _make_csv(
        [
            ["RALC", "Nom", "Cognoms"],
            ["3001", "First", "Row"],
            ["3001", "Duplicate", "Row"],
        ]
    )
    files = {"file": ("alumnes.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/imports/alumnes", headers=h, files=files)
    assert r.status_code == 201
    body = r.json()
    assert body["ok"] == 1
    assert body["errors"] == 1


async def _setup_for_notes_import(client: AsyncClient, h: dict) -> dict:
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
    ra = (
        await client.post(
            "/api/v1/ras",
            headers=h,
            json={
                "modul_id": modul["id"],
                "ordre": 1,
                "codi": "RA1",
                "descripcio": "x",
                "pes": 100,
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
            json={"ralc": "R1", "dni": "11111111H", "nom": "A", "cognoms": "B"},
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
    aval = (
        await client.post(
            "/api/v1/avaluacions",
            headers=h,
            json={"curs_acad_id": curs["id"], "nom": "1a", "ordre": 1},
        )
    ).json()
    return {"modul_id": modul["id"], "aval_id": aval["id"], "ra_codi": ra["codi"]}


async def test_notes_import_rejects_out_of_range(
    client: AsyncClient, db, storage_root
) -> None:
    """Notes import: a value > 10 or < 0 is an error row, not a clamp warning."""
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_for_notes_import(client, h)

    csv_bytes = _make_csv(
        [
            ["DNI", "Nom", "RA1"],
            ["11111111H", "A B", "12.5"],  # > 10 → error
        ]
    )
    files = {"file": ("notes.csv", csv_bytes, "text/csv")}
    r = await client.post(
        "/api/v1/imports/notes",
        headers=h,
        data={"modul_id": ctx["modul_id"], "avaluacio_id": ctx["aval_id"]},
        files=files,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["errors"] == 1
    err_row = next(p for p in body["preview"] if p["errors"])
    assert any("fora de rang" in e for e in err_row["errors"])


async def test_notes_import_rejects_non_numeric(
    client: AsyncClient, db, storage_root
) -> None:
    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup_for_notes_import(client, h)
    csv_bytes = _make_csv([["DNI", "RA1"], ["11111111H", "ABC"]])
    files = {"file": ("notes.csv", csv_bytes, "text/csv")}
    r = await client.post(
        "/api/v1/imports/notes",
        headers=h,
        data={"modul_id": ctx["modul_id"], "avaluacio_id": ctx["aval_id"]},
        files=files,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["errors"] == 1


async def test_only_admin_can_import(client: AsyncClient, db, storage_root) -> None:
    from tests.factories import make_user

    await make_user(db, dni="55555555E", password="Prof-Pwd-1!")
    login = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    csv_bytes = _make_csv([["RALC", "Nom", "Cognoms"], ["1", "x", "y"]])
    files = {"file": ("a.csv", csv_bytes, "text/csv")}
    r = await client.post("/api/v1/imports/alumnes", headers=h, files=files)
    assert r.status_code == 403


async def test_audit_log_admin_only(client: AsyncClient, db) -> None:
    from tests.factories import make_user

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}

    # The admin login itself produced an audit row
    r = await client.get("/api/v1/audit-logs", headers=h)
    assert r.status_code == 200
    assert any(row["action"] == "login_success" for row in r.json())

    # Professor cannot access
    await make_user(db, dni="55555555E", password="Prof-Pwd-1!")
    plogin = await client.post(
        "/api/v1/auth/login", json={"identifier": "55555555E", "password": "Prof-Pwd-1!"}
    )
    ph = {"Authorization": f"Bearer {plogin.json()['access_token']}"}
    r2 = await client.get("/api/v1/audit-logs", headers=ph)
    assert r2.status_code == 403
