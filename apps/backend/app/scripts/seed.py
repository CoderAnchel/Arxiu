"""Realistic seed data for local dev / demo. Idempotent — safe to re-run.

Outputs the initial admin password to stdout AND writes a seed_credentials.csv
with all generated passwords (gitignored).

Run:
    docker compose ... exec backend python -m app.scripts.seed
or:
    make seed
"""
from __future__ import annotations

import asyncio
import csv
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import security
from app.db.session import get_engine
from app.models.catalog import (
    Cicle,
    CursAcademic,
    FamiliaProfessional,
    Modul,
    Nivell,
    Ra,
)
from app.models.grading import Avaluacio, EstatAvaluacio, QualificacioRa
from app.models.people import (
    Alumne,
    AssignacioDocent,
    EstatMatricula,
    GrupClasse,
    Matricula,
    TipusGrup,
    TutorLegal,
)
from app.models.user import User, UserRole

CRED_FILE = Path("seed_credentials.csv")


async def _get_or_create(session: AsyncSession, model, **kw):  # type: ignore[no-untyped-def]
    """Find a row matching kw['lookup_keys'], or create with kw['defaults']."""
    lookup = kw.pop("lookup")
    defaults = kw.pop("defaults", {})
    stmt = select(model)
    for k, v in lookup.items():
        stmt = stmt.where(getattr(model, k) == v)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing, False
    obj = model(**lookup, **defaults)
    session.add(obj)
    await session.flush()
    return obj, True


async def main() -> None:
    engine = get_engine()
    SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    creds: list[dict[str, str]] = []

    async with SessionFactory() as session:
        # --- Admin -----------------------------------------------------------
        admin, created = await _get_or_create(
            session,
            User,
            lookup={"dni": "00000000T"},
            defaults={
                "email": "admin@inslaferreria.cat",
                "nom": "Sergi",
                "cognoms": "Veciana",
                "departament": "Direcció",
                "role": UserRole.ADMIN,
                "active": True,
                "must_change_password": True,
            },
        )
        if created or admin.password_hash is None:
            # If the operator pre-generated a password (e.g. via the Windows
            # bootstrap script), respect it so they can announce it before the
            # seed runs. Otherwise fall back to a freshly generated one.
            import os as _os
            admin_pw = _os.environ.get("ADMIN_INITIAL_PASSWORD") or security.generate_password()
            admin.password_hash = security.hash_password(admin_pw)
            admin.password_set_at = datetime.now(timezone.utc)
            admin.must_change_password = True
            creds.append(
                {"role": "admin", "dni": admin.dni, "email": admin.email, "password": admin_pw}
            )
            print(f"\n  → admin created: DNI={admin.dni} password={admin_pw}\n")
        else:
            print(f"  ✓ admin {admin.dni} already exists (skipping password change)")

        # --- Família professional -------------------------------------------
        familia, _ = await _get_or_create(
            session,
            FamiliaProfessional,
            lookup={"codi": "INF"},
            defaults={"nom": "Informàtica i Comunicacions"},
        )
        familia2, _ = await _get_or_create(
            session,
            FamiliaProfessional,
            lookup={"codi": "ADM"},
            defaults={"nom": "Administració i Gestió"},
        )

        # --- Cicles ----------------------------------------------------------
        cicle_dam, _ = await _get_or_create(
            session, Cicle,
            lookup={"codi": "DAM"},
            defaults={"nom": "Desenvolupament d'Aplicacions Multiplataforma",
                      "familia_id": familia.id, "nivell": Nivell.SUPERIOR, "durada": 2},
        )
        cicle_smx, _ = await _get_or_create(
            session, Cicle,
            lookup={"codi": "SMX"},
            defaults={"nom": "Sistemes Microinformàtics i Xarxes",
                      "familia_id": familia.id, "nivell": Nivell.MIG, "durada": 2},
        )

        # --- Mòduls + RAs ---------------------------------------------------
        async def ensure_modul(cicle, codi, nom, curs, hores, ras_data):  # type: ignore[no-untyped-def]
            mod, _ = await _get_or_create(
                session, Modul,
                lookup={"cicle_id": cicle.id, "codi": codi},
                defaults={"nom": nom, "curs": curs, "hores": hores},
            )
            for ordre, (codi_ra, desc, pes) in enumerate(ras_data, start=1):
                await _get_or_create(
                    session, Ra,
                    lookup={"modul_id": mod.id, "ordre": ordre},
                    defaults={"codi": codi_ra, "descripcio": desc, "pes": Decimal(pes)},
                )
            return mod

        m_dam_03 = await ensure_modul(
            cicle_dam, "M03", "Programació", 1, 264,
            [
                ("RA1", "Identifica els elements del llenguatge.", "20"),
                ("RA2", "Aplica estructures de control.", "30"),
                ("RA3", "Programa amb classes i objectes.", "30"),
                ("RA4", "Manipula col·leccions de dades.", "20"),
            ],
        )
        m_dam_06 = await ensure_modul(
            cicle_dam, "M06", "Accés a dades", 2, 165,
            [
                ("RA1", "Treballa amb fitxers seqüencials.", "25"),
                ("RA2", "Connecta amb bases de dades relacionals.", "40"),
                ("RA3", "Aplica ORMs.", "35"),
            ],
        )
        m_smx_02 = await ensure_modul(
            cicle_smx, "M02", "Sistemes Operatius Monolloc", 1, 198,
            [
                ("RA1", "Instal·la sistemes operatius.", "30"),
                ("RA2", "Gestiona usuaris i permisos.", "35"),
                ("RA3", "Configura programari de sistema.", "35"),
            ],
        )

        # --- Curs acadèmic --------------------------------------------------
        curs_actual, _ = await _get_or_create(
            session, CursAcademic,
            lookup={"nom": "2025-2026"},
            defaults={"actiu": True, "data_inici": date(2025, 9, 13), "data_fi": date(2026, 6, 21)},
        )

        # --- Docents (professors) -------------------------------------------
        docents_data = [
            ("12345678A", "nuria.bonet@inslaferreria.cat",   "Núria",  "Bonet",     "Informàtica"),
            ("23456789B", "marta.puig@inslaferreria.cat",    "Marta",  "Puig",      "Informàtica"),
            ("34567890C", "pere.fontana@inslaferreria.cat",  "Pere",   "Fontana",   "Informàtica"),
            ("45678901D", "anna.carbo@inslaferreria.cat",    "Anna",   "Carbó",     "Informàtica"),
            ("56789012E", "david.mestre@inslaferreria.cat",  "David",  "Mestre",    "Informàtica"),
        ]

        docents = []
        for dni, email, nom, cognoms, dept in docents_data:
            docent, was_new = await _get_or_create(
                session, User,
                lookup={"dni": dni},
                defaults={
                    "email": email, "nom": nom, "cognoms": cognoms,
                    "departament": dept, "role": UserRole.PROFESSOR, "active": True,
                    "must_change_password": True,
                },
            )
            if was_new or docent.password_hash is None:
                pw = security.generate_password()
                docent.password_hash = security.hash_password(pw)
                docent.password_set_at = datetime.now(timezone.utc)
                docent.must_change_password = True
                creds.append({"role": "professor", "dni": dni, "email": email, "password": pw})
            docents.append(docent)

        await session.flush()

        # --- Grups ----------------------------------------------------------
        grup_dam1a, _ = await _get_or_create(
            session, GrupClasse,
            lookup={"codi": "DAM1A", "curs_acad_id": curs_actual.id},
            defaults={"cicle_id": cicle_dam.id, "curs": 1, "tutor_user_id": docents[0].id},
        )
        grup_smx1a, _ = await _get_or_create(
            session, GrupClasse,
            lookup={"codi": "SMX1A", "curs_acad_id": curs_actual.id},
            defaults={"cicle_id": cicle_smx.id, "curs": 1, "tutor_user_id": docents[1].id},
        )

        # --- Assignacions docents -------------------------------------------
        # Tots els 5 profes tenen alguna assignació al grup DAM1A o SMX1A
        # (que són els únics grups de 1r curs creats per aquesta seed).
        # IMPORTANT: el curs del mòdul i el del grup han de coincidir; M06
        # és de 2n curs, així que no es pot assignar a DAM1A (1r curs).
        assigs = [
            (docents[0], grup_dam1a, m_dam_03),
            (docents[1], grup_smx1a, m_smx_02),
            (docents[2], grup_dam1a, m_dam_03),
            (docents[3], grup_dam1a, m_dam_03),
            (docents[4], grup_smx1a, m_smx_02),
        ]
        for user, grup, modul in assigs:
            assert grup.curs == modul.curs, (
                f"seed inconsistent: grup {grup.codi} curs={grup.curs} "
                f"vs mòdul {modul.codi} curs={modul.curs}"
            )
            await _get_or_create(
                session, AssignacioDocent,
                lookup={
                    "user_id": user.id, "grup_id": grup.id,
                    "modul_id": modul.id, "curs_acad_id": curs_actual.id,
                },
                defaults={},
            )

        # Clean up any historically-bad assignacions that may have been
        # persisted by earlier seed runs (e.g. DAM1A · M06 when M06 is 2n curs).
        bad = await session.execute(
            select(AssignacioDocent)
            .join(Modul, Modul.id == AssignacioDocent.modul_id)
            .join(GrupClasse, GrupClasse.id == AssignacioDocent.grup_id)
            .where(
                AssignacioDocent.deleted_at.is_(None),
                Modul.curs != GrupClasse.curs,
            )
        )
        for a in bad.scalars().all():
            a.deleted_at = datetime.now(timezone.utc)

        # Hard-delete orphan qualificacions_ra (matricula.curs != modul.curs):
        # these are notes saved against an invalid assignment and never had
        # academic meaning — they would only confuse the archive.
        bad_qr = await session.execute(
            select(QualificacioRa)
            .join(Matricula, Matricula.id == QualificacioRa.matricula_id)
            .join(Ra, Ra.id == QualificacioRa.ra_id)
            .join(Modul, Modul.id == Ra.modul_id)
            .where(Matricula.curs != Modul.curs)
        )
        for qr in bad_qr.scalars().all():
            await session.delete(qr)

        # --- Alumnes + matricules -------------------------------------------
        alumnes_data = [
            # (ralc, dni, nom, cognoms, email, tutor_email)
            ("R0000001", "11111111H", "Aleix",  "Vilanova",      "aleix.v@alumnes.cat",  "tutor1@gmail.com"),
            ("R0000002", "22222222J", "Berta",  "Puigdomènech",  "berta.p@alumnes.cat",  "tutor2@gmail.com"),
            ("R0000003", "33333333K", "Marc",   "Riera",          "marc.r@alumnes.cat",   "tutor3@gmail.com"),
            ("R0000004", "44444444L", "Júlia",  "Carbonell",      "julia.c@alumnes.cat",  "tutor4@gmail.com"),
            ("R0000005", "55555555M", "Pol",    "Fontana",        "pol.f@alumnes.cat",    None),
            ("R0000006", "66666666N", "Anna",   "Soler",          "anna.s@alumnes.cat",   "tutor6@gmail.com"),
            ("R0000007", "77777777P", "Bru",    "Ribas",          "bru.r@alumnes.cat",    "tutor7@gmail.com"),
            ("R0000008", "88888888Q", "Clara",  "Mas",            "clara.m@alumnes.cat",  "tutor8@gmail.com"),
        ]
        alumnes_dam = []
        for ralc, dni, nom, cognoms, email, tutor_email in alumnes_data[:5]:
            alumne, was_new = await _get_or_create(
                session, Alumne,
                lookup={"ralc": ralc},
                defaults={"dni": dni, "nom": nom, "cognoms": cognoms, "email": email,
                          "data_naixement": date(2007, 3, 15)},
            )
            if was_new and tutor_email:
                # Async-safe: insert directly with alumne_id rather than touching
                # the lazy `tutors_legals` collection.
                session.add(TutorLegal(
                    alumne_id=alumne.id, nom=f"Tutor/a de {nom}", email=tutor_email
                ))
            alumnes_dam.append(alumne)

        alumnes_smx = []
        for ralc, dni, nom, cognoms, email, tutor_email in alumnes_data[5:]:
            alumne, was_new = await _get_or_create(
                session, Alumne,
                lookup={"ralc": ralc},
                defaults={"dni": dni, "nom": nom, "cognoms": cognoms, "email": email,
                          "data_naixement": date(2008, 6, 22)},
            )
            if was_new and tutor_email:
                session.add(TutorLegal(
                    alumne_id=alumne.id, nom=f"Tutor/a de {nom}", email=tutor_email
                ))
            alumnes_smx.append(alumne)

        await session.flush()

        # Matricules
        for a in alumnes_dam:
            await _get_or_create(
                session, Matricula,
                lookup={"alumne_id": a.id, "curs_acad_id": curs_actual.id, "cicle_id": cicle_dam.id},
                defaults={"grup_id": grup_dam1a.id, "curs": 1,
                          "tipus": TipusGrup.PRIMARI, "estat": EstatMatricula.ACTIU},
            )
        for a in alumnes_smx:
            await _get_or_create(
                session, Matricula,
                lookup={"alumne_id": a.id, "curs_acad_id": curs_actual.id, "cicle_id": cicle_smx.id},
                defaults={"grup_id": grup_smx1a.id, "curs": 1,
                          "tipus": TipusGrup.PRIMARI, "estat": EstatMatricula.ACTIU},
            )

        # --- Avaluacions ----------------------------------------------------
        AVAL_DATES = {
            1: date(2025, 9, 15),    # 1a — inici de curs
            2: date(2025, 12, 15),   # 2a — desembre
            3: date(2026, 3, 15),    # 3a — març
        }
        for ordre, (nom, estat) in enumerate(
            [("1a Avaluació", EstatAvaluacio.DOCENT),
             ("2a Avaluació", EstatAvaluacio.OBERTA),
             ("3a Avaluació", EstatAvaluacio.OBERTA)],
            start=1,
        ):
            await _get_or_create(
                session, Avaluacio,
                lookup={"curs_acad_id": curs_actual.id, "ordre": ordre},
                defaults={"nom": nom, "estat": estat,
                          "data_inici": AVAL_DATES[ordre]},
            )

        await session.commit()

    # --- Write credentials CSV ----------------------------------------------
    if creds:
        with CRED_FILE.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["role", "dni", "email", "password"])
            w.writeheader()
            w.writerows(creds)
        print(f"\n  ✓ Wrote {len(creds)} credential(s) to {CRED_FILE.resolve()}")
        print(f"  ⚠️  Aquest fitxer NO ha de fer-se commit (ja està al .gitignore).\n")

    print("Seed completat.")
    print()
    print("LOGIN:  https://localhost (or http://localhost:5173 in dev)")
    print(f"  ADMIN  → DNI: 00000000T")
    if creds:
        admin_cred = next((c for c in creds if c["role"] == "admin"), None)
        if admin_cred:
            print(f"  ADMIN  → password (canvia-la al primer accés): {admin_cred['password']}")
    print()


def _flush_creds_on_exit(creds_ref):  # type: ignore[no-untyped-def]
    """Best-effort write of credentials even if main() raised — important
    so the admin password isn't lost if a later step fails."""
    try:
        if creds_ref:
            with CRED_FILE.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=["role", "dni", "email", "password"])
                w.writeheader()
                w.writerows(creds_ref)
            print(f"\n  ⚠️  Seed va fallar però s'han escrit {len(creds_ref)} credencial(s) a {CRED_FILE.resolve()}\n")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
