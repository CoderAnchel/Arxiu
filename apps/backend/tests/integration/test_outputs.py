"""Phase-4 outputs: butlleti generation + email send.

WeasyPrint is monkeypatched (its system deps are container-only). aiosmtplib
send is also patched so we can assert the message and simulate failures.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.enviaments import EstatEnviament
from app.services import butlleti as butlleti_module
from app.services import email as email_module
from tests.factories import make_admin


async def _admin_token(client: AsyncClient, db) -> str:
    await make_admin(db, dni="00000000T", password="Admin-Pwd-1!")
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": "00000000T", "password": "Admin-Pwd-1!"}
    )
    return r.json()["access_token"]


async def _setup(client: AsyncClient, token: str) -> dict:
    """Create curs + cicle + modul + ra + grup + alumne + matricula + avaluació."""
    from app.models.people import Alumne, Matricula, TutorLegal

    h = {"Authorization": f"Bearer {token}"}
    curs = (await client.post("/api/v1/cursos-academics", headers=h,
                              json={"nom": "2025-2026", "actiu": True})).json()
    cicle = (await client.post("/api/v1/cicles", headers=h,
                               json={"codi": "DAM", "nom": "DAM", "nivell": "superior"})).json()
    modul = (await client.post("/api/v1/moduls", headers=h,
                               json={"cicle_id": cicle["id"], "codi": "M03",
                                     "nom": "Programació", "curs": 1, "hores": 264})).json()
    ra = (await client.post("/api/v1/ras", headers=h,
                            json={"modul_id": modul["id"], "ordre": 1, "codi": "RA1",
                                  "descripcio": "x", "pes": 25})).json()
    grup = (await client.post("/api/v1/grups", headers=h,
                              json={"codi": "DAM1A", "curs_acad_id": curs["id"],
                                    "cicle_id": cicle["id"], "curs": 1})).json()
    aval = (await client.post("/api/v1/avaluacions", headers=h,
                              json={"curs_acad_id": curs["id"], "nom": "1a Avaluació", "ordre": 1})).json()
    return {**{f"{k}_id": v["id"] for k, v in dict(
        curs=curs, cicle=cicle, modul=modul, ra=ra, grup=grup, aval=aval
    ).items()}}


@pytest.fixture
def mock_pdf(monkeypatch):
    async def fake(_session, *, alumne_id, avaluacio_id, opts=None):
        # Render the HTML template (still exercises Jinja) but skip WeasyPrint.
        html = await butlleti_module.render_butlleti_html(
            _session, alumne_id=alumne_id, avaluacio_id=avaluacio_id, opts=opts
        )
        return f"%PDF-1.4\n{html[:200]}".encode()

    monkeypatch.setattr(butlleti_module, "render_butlleti_pdf", fake)
    yield


@pytest.fixture
def mock_smtp(monkeypatch):
    sent: list[dict] = []

    async def fake_send(msg, **kw):  # type: ignore[no-untyped-def]
        sent.append(
            {
                "to": msg["To"],
                "subject": msg["Subject"],
                "body": str(msg.get_body(("plain",))),
                "host": kw.get("hostname"),
            }
        )

    import aiosmtplib

    monkeypatch.setattr(aiosmtplib, "send", fake_send)
    yield sent


# ---------------------------------------------------------------------------

async def test_butlleti_generate_zip(client: AsyncClient, db, mock_pdf) -> None:
    from app.models.people import Alumne, Matricula

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, token)

    alumne = Alumne(ralc="0000000001", nom="Aleix", cognoms="Test")
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)
    db.add(Matricula(alumne_id=alumne.id, grup_id=ctx["grup_id"], cicle_id=ctx["cicle_id"],
                     curs=1, curs_acad_id=ctx["curs_id"]))
    await db.commit()

    r = await client.post(
        "/api/v1/butlletins/generate", headers=h,
        json={"avaluacio_id": ctx["aval_id"], "alumne_ids": [alumne.id]},
    )
    # With one alumne and inline=false (default), still returns ZIP
    assert r.status_code == 200, r.text
    assert "zip" in r.headers["content-type"]
    assert r.headers["x-generated"] == "1"


async def test_butlleti_send_logs_enviaments(client: AsyncClient, db, mock_pdf, mock_smtp) -> None:
    from app.models.people import Alumne, Matricula, TutorLegal

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, token)

    alumne = Alumne(
        ralc="0000000002", nom="Berta", cognoms="Test",
        email="berta@example.com",
        tutors_legals=[TutorLegal(nom="Tutor 1", email="tutor1@example.com")],
    )
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)
    db.add(Matricula(alumne_id=alumne.id, grup_id=ctx["grup_id"], cicle_id=ctx["cicle_id"],
                     curs=1, curs_acad_id=ctx["curs_id"]))
    await db.commit()

    r = await client.post(
        "/api/v1/enviaments/butlletins", headers=h,
        json={"avaluacio_id": ctx["aval_id"], "alumne_ids": [alumne.id],
              "send_to": ["alumne", "tutors"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sent"] == 2
    assert body["failed"] == 0
    assert {x["destinatari_email"] for x in body["results"]} == {
        "berta@example.com",
        "tutor1@example.com",
    }

    # Same emails should appear in the SMTP fake
    assert {m["to"] for m in mock_smtp} == {"berta@example.com", "tutor1@example.com"}

    # And the enviaments table
    listing = await client.get("/api/v1/enviaments", headers=h)
    assert listing.status_code == 200
    items = listing.json()
    assert len(items) == 2
    assert all(it["estat"] == EstatEnviament.ENVIAT.value for it in items)


async def test_butlleti_send_skips_alumnes_without_email(
    client: AsyncClient, db, mock_pdf, mock_smtp
) -> None:
    from app.models.people import Alumne, Matricula

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, token)

    alumne = Alumne(ralc="0000000003", nom="C", cognoms="Test", email=None)
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)
    db.add(Matricula(alumne_id=alumne.id, grup_id=ctx["grup_id"], cicle_id=ctx["cicle_id"],
                     curs=1, curs_acad_id=ctx["curs_id"]))
    await db.commit()

    r = await client.post(
        "/api/v1/enviaments/butlletins", headers=h,
        json={"avaluacio_id": ctx["aval_id"], "alumne_ids": [alumne.id], "send_to": ["alumne"]},
    )
    assert r.status_code == 200
    assert r.json()["sent"] == 0
    assert r.json()["failed"] == 0
    assert mock_smtp == []


async def test_resend_only_for_error_or_rebotat(
    client: AsyncClient, db, mock_pdf, mock_smtp
) -> None:
    from app.models.enviaments import Enviament, TipusEnviament
    from app.models.people import Alumne

    token = await _admin_token(client, db)
    h = {"Authorization": f"Bearer {token}"}
    ctx = await _setup(client, token)

    alumne = Alumne(ralc="0000000004", nom="D", cognoms="Test", email="d@example.com")
    db.add(alumne)
    await db.commit()
    await db.refresh(alumne)

    # Manually insert an enviament in 'enviat' state
    env = Enviament(
        alumne_id=alumne.id, destinatari_email="d@example.com",
        tipus=TipusEnviament.BUTLLETI, assumpte="x",
        avaluacio_id=ctx["aval_id"], estat=EstatEnviament.ENVIAT,
    )
    db.add(env)
    await db.commit()
    await db.refresh(env)

    r = await client.post(f"/api/v1/enviaments/{env.id}/resend", headers=h)
    assert r.status_code == 409  # not_resendable
