"""Butlletí endpoints — synchronous PDF generation + email send.

Phase 4 keeps generation synchronous (a single butlletí takes <1s; generating
30 alumnes takes ~10–15s, well within the request timeout for an admin tool).
A future Phase 4 follow-up moves generation to ARQ for very large batches.
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from fastapi.responses import Response

from app.api.v1.deps import CurrentUser, DbSession, get_request_metadata
from app.core.exceptions import ArxiuError, NotFound
from app.models.enviaments import Enviament, EstatEnviament, TipusEnviament
from app.models.grading import Avaluacio
from app.models.people import Alumne
from app.schemas.outputs import (
    ButlletiGenerateRequest,
    ButlletiGenerateResponse,
    ButlletiGenerateResultRow,
    ButlletiSendRequest,
    ButlletiSendResponse,
    ButlletiSendResultRow,
)
from app.services import audit
from app.services.butlleti import (
    ButlletiOpts,
    render_butlleti_email,
    render_butlleti_pdf,
)
from app.services.email import send_butlleti

router = APIRouter(tags=["outputs"])


def _opts_from_schema(o) -> ButlletiOpts:  # type: ignore[no-untyped-def]
    return ButlletiOpts(
        detall_ra=o.detall_ra,
        comentaris=o.comentaris,
        distribucio_grup=o.distribucio_grup,
        signatura=o.signatura,
        logo_centre=o.logo_centre,
    )


def _pdf_filename(alumne: Alumne, avaluacio: Avaluacio) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in f"{alumne.cognoms}_{alumne.nom}")
    return f"butlleti_{safe}_{avaluacio.nom.replace(' ', '_')}.pdf"


# ---------------------------------------------------------------------------
@router.get(
    "/butlletins/preview/{alumne_id}/{avaluacio_id}",
    responses={200: {"content": {"application/pdf": {}}}},
)
async def preview_butlleti(
    db: DbSession,
    _: CurrentUser,
    alumne_id: int = Path(..., ge=1),
    avaluacio_id: int = Path(..., ge=1),
):
    try:
        pdf_bytes = await render_butlleti_pdf(
            db, alumne_id=alumne_id, avaluacio_id=avaluacio_id
        )
    except ArxiuError as exc:
        raise HTTPException(exc.http_status, exc.code) from exc

    alumne = await db.get(Alumne, alumne_id)
    avaluacio = await db.get(Avaluacio, avaluacio_id)
    assert alumne is not None and avaluacio is not None
    return Response(
        pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{_pdf_filename(alumne, avaluacio)}"'
        },
    )


# ---------------------------------------------------------------------------
@router.post(
    "/butlletins/generate",
    response_model=None,
    responses={200: {"content": {"application/zip": {}}}},
)
async def generate_butlletins(
    payload: ButlletiGenerateRequest,
    request: Request,
    db: DbSession,
    actor: CurrentUser,
    inline: bool = Query(default=False),
):
    """Generate PDFs for the given alumnes. If `inline=true` and a single alumne
    is requested, returns a single PDF; otherwise returns a ZIP archive.
    """
    avaluacio = await db.get(Avaluacio, payload.avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "avaluacio_not_found")

    opts = _opts_from_schema(payload.opts)
    rows: list[ButlletiGenerateResultRow] = []
    pdf_blobs: list[tuple[str, bytes]] = []

    for alumne_id in payload.alumne_ids:
        alumne = await db.get(Alumne, alumne_id)
        if alumne is None or alumne.deleted_at is not None:
            rows.append(
                ButlletiGenerateResultRow(alumne_id=alumne_id, ok=False, error="alumne_not_found")
            )
            continue
        try:
            pdf = await render_butlleti_pdf(
                db, alumne_id=alumne_id, avaluacio_id=payload.avaluacio_id, opts=opts
            )
        except NotFound as exc:
            rows.append(
                ButlletiGenerateResultRow(alumne_id=alumne_id, ok=False, error=exc.code)
            )
            continue
        except Exception as exc:  # pragma: no cover
            rows.append(
                ButlletiGenerateResultRow(alumne_id=alumne_id, ok=False, error=str(exc)[:200])
            )
            continue

        filename = _pdf_filename(alumne, avaluacio)
        pdf_blobs.append((filename, pdf))
        rows.append(
            ButlletiGenerateResultRow(
                alumne_id=alumne_id, ok=True, filename=filename, size_bytes=len(pdf)
            )
        )

    await audit.record(
        db,
        action="butlletins_generated",
        entity="avaluacio",
        entity_id=payload.avaluacio_id,
        user_id=actor.id,
        after={
            "total": len(payload.alumne_ids),
            "ok": sum(1 for r in rows if r.ok),
            "failed": sum(1 for r in rows if not r.ok),
        },
        **get_request_metadata(request),
    )

    # Single-alumne, inline=true → stream PDF directly
    if inline and len(pdf_blobs) == 1:
        filename, pdf = pdf_blobs[0]
        return Response(
            pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    # Otherwise — JSON summary if no PDFs (all errors), else ZIP
    if not pdf_blobs:
        return ButlletiGenerateResponse(
            results=rows,
            generated=0,
            failed=len(rows),
        )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, pdf in pdf_blobs:
            zf.writestr(filename, pdf)
    buf.seek(0)

    zip_name = f"butlletins_{avaluacio.nom.replace(' ', '_')}.zip"
    return Response(
        buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "X-Generated": str(len(pdf_blobs)),
            "X-Failed": str(sum(1 for r in rows if not r.ok)),
        },
    )


# ---------------------------------------------------------------------------
@router.post("/enviaments/butlletins", response_model=ButlletiSendResponse)
async def send_butlletins(
    payload: ButlletiSendRequest,
    request: Request,
    db: DbSession,
    actor: CurrentUser,
):
    avaluacio = await db.get(Avaluacio, payload.avaluacio_id)
    if avaluacio is None or avaluacio.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "avaluacio_not_found")

    opts = _opts_from_schema(payload.opts)
    results: list[ButlletiSendResultRow] = []

    for alumne_id in payload.alumne_ids:
        alumne = await db.get(Alumne, alumne_id)
        if alumne is None or alumne.deleted_at is not None:
            continue

        # Determine recipients
        recipients: list[str] = []
        if "alumne" in payload.send_to and alumne.email:
            recipients.append(alumne.email)
        if "tutors" in payload.send_to:
            for t in alumne.tutors_legals:
                if t.email:
                    recipients.append(t.email)

        if not recipients:
            continue

        # Generate the PDF once
        try:
            pdf = await render_butlleti_pdf(
                db, alumne_id=alumne_id, avaluacio_id=payload.avaluacio_id, opts=opts
            )
        except NotFound as exc:
            for to in recipients:
                env = Enviament(
                    alumne_id=alumne_id,
                    destinatari_email=to,
                    tipus=TipusEnviament.BUTLLETI,
                    assumpte=f"Butlletí · {avaluacio.nom}",
                    avaluacio_id=avaluacio.id,
                    created_by_user_id=actor.id,
                    estat=EstatEnviament.ERROR,
                    error_msg=exc.code,
                )
                db.add(env)
                await db.flush()
                results.append(
                    ButlletiSendResultRow(
                        alumne_id=alumne_id,
                        destinatari_email=to,
                        enviament_id=env.id,
                        estat=EstatEnviament.ERROR,
                        error=exc.code,
                    )
                )
            continue

        # Render email body
        nom_complet = f"{alumne.nom} {alumne.cognoms}"
        grup_codi = alumne.tutors_legals[0].nom if False else ""  # not used; keep signature
        # Look up grup via matricula
        from sqlalchemy import select  # localised import

        from app.models.people import GrupClasse, Matricula
        matr = (
            await db.execute(
                select(Matricula).where(
                    Matricula.alumne_id == alumne_id,
                    Matricula.curs_acad_id == avaluacio.curs_acad_id,
                    Matricula.deleted_at.is_(None),
                ).limit(1)
            )
        ).scalar_one_or_none()
        grup_codi = ""
        if matr is not None:
            grup = await db.get(GrupClasse, matr.grup_id)
            if grup is not None:
                grup_codi = grup.codi
        curs_acad_nom = avaluacio.curs_acad.nom if avaluacio.curs_acad else ""

        assumpte = f"Butlletí · {avaluacio.nom} · {nom_complet}"
        plain_body = (
            f"Benvolguts/des,\n\n"
            f"Adjuntem el butlletí de qualificacions de {nom_complet} ({grup_codi}) "
            f"corresponent a {avaluacio.nom}.\n\n"
            f"Per a qualsevol consulta, podeu contactar amb la coordinació del centre.\n\n"
            f"— Institut la Ferreria"
        )
        html_body = render_butlleti_email(
            assumpte=assumpte,
            alumne_nom_complet=nom_complet,
            grup_codi=grup_codi,
            avaluacio_nom=avaluacio.nom,
            curs_acad_nom=curs_acad_nom,
        )

        for to in recipients:
            env = Enviament(
                alumne_id=alumne_id,
                destinatari_email=to,
                tipus=TipusEnviament.BUTLLETI,
                assumpte=assumpte,
                avaluacio_id=avaluacio.id,
                adjunt_filename=_pdf_filename(alumne, avaluacio),
                created_by_user_id=actor.id,
                queued_at=datetime.now(timezone.utc),
            )
            db.add(env)
            await db.flush()

            await send_butlleti(
                session=db,
                enviament=env,
                pdf_bytes=pdf,
                plain_body=plain_body,
                html_body=html_body,
            )
            await db.flush()

            results.append(
                ButlletiSendResultRow(
                    alumne_id=alumne_id,
                    destinatari_email=to,
                    enviament_id=env.id,
                    estat=env.estat,
                    error=env.error_msg,
                )
            )

    await audit.record(
        db,
        action="butlletins_sent",
        entity="avaluacio",
        entity_id=payload.avaluacio_id,
        user_id=actor.id,
        after={
            "alumnes": len(payload.alumne_ids),
            "results": len(results),
            "sent": sum(1 for r in results if r.estat == EstatEnviament.ENVIAT),
            "failed": sum(1 for r in results if r.estat != EstatEnviament.ENVIAT),
        },
        **get_request_metadata(request),
    )

    return ButlletiSendResponse(
        results=results,
        sent=sum(1 for r in results if r.estat == EstatEnviament.ENVIAT),
        failed=sum(1 for r in results if r.estat != EstatEnviament.ENVIAT),
    )
