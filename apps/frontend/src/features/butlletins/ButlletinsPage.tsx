/** Butlletins — alumne selection + options + preview + generate/send.
 *
 * Layout (3-col desktop):
 *   ┌──────────────┬─────────────┬──────────────┐
 *   │  Alumnes     │  Opcions    │  Preview     │
 *   │  (checkbox)  │  (toggles)  │  (PDF iframe)│
 *   └──────────────┴─────────────┴──────────────┘
 *   [Generar PDFs (ZIP)]  [Enviar emails]
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { authApi } from "@/api/auth";
import { catalogApi, type CursAcademic } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { gradingApi, type Avaluacio } from "@/api/grading";
import { grupsApi } from "@/api/grups";
import { outputsApi, DEFAULT_OPTS, type ButlletiOpts } from "@/api/outputs";
import { peopleApi, type Alumne } from "@/api/people";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./ButlletinsPage.module.css";

export function ButlletinsPage() {
  const accessToken = useAuthStore(s => s.accessToken);
  const isAdmin = useAuthStore(s => s.user?.role === "admin");
  const myAssigs = useQuery({
    queryKey: ["my-assignacions"],
    queryFn: () => authApi.myAssignacions(),
  });
  const [searchParams] = useSearchParams();
  const urlCurs = searchParams.get("curs");
  const urlGrup = searchParams.get("grup");

  // --- selectors ---------------------------------------------------------

  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const [cursId, setCursId] = useState<number | null>(null);
  useEffect(() => {
    if (cursId !== null) return;
    if (urlCurs && cursos.data?.some(c => c.id === Number(urlCurs))) {
      setCursId(Number(urlCurs));
      return;
    }
    const actiu = cursos.data?.find((c: CursAcademic) => c.actiu) ?? cursos.data?.[0];
    if (actiu) setCursId(actiu.id);
  }, [cursId, cursos.data, urlCurs]);

  const grups = useQuery({
    queryKey: ["grups", cursId],
    queryFn: () => grupsApi.list(cursId ?? undefined),
    enabled: cursId !== null,
  });
  const [grupId, setGrupId] = useState<number | null>(null);
  useEffect(() => {
    if (grupId !== null || !grups.data || grups.data.length === 0) return;
    if (urlGrup && grups.data.some(g => g.id === Number(urlGrup))) {
      setGrupId(Number(urlGrup));
      return;
    }
    setGrupId(grups.data[0]!.id);
  }, [grupId, grups.data, urlGrup]);

  const avals = useQuery({
    queryKey: ["avaluacions", cursId],
    queryFn: () => gradingApi.listAvaluacions(cursId ?? undefined),
    enabled: cursId !== null,
  });
  const [avalId, setAvalId] = useState<number | null>(null);
  useEffect(() => {
    if (avalId === null && avals.data && avals.data.length > 0) {
      // Prefer tancada (final state) for butlletins
      const tancada = avals.data.find(a => a.estat === "tancada") ?? avals.data[0]!;
      setAvalId(tancada.id);
    }
  }, [avalId, avals.data]);

  // --- alumnes (loaded by grup) -----------------------------------------
  // Phase 4 lite: fetch all alumnes and intersect with the matrícules of the grup
  // via the matricules listing endpoint. To keep the wire simple we use the
  // existing /alumnes search endpoint, then filter to those with a matricula
  // in this grup. A cleaner alternative is a future GET /grups/{id}/alumnes.
  const alumnesAll = useQuery({
    queryKey: ["alumnes-for-butlleti"],
    queryFn: () => peopleApi.listAlumnes({ limit: 500 }),
  });
  // For Phase 4 we treat all loaded alumnes as candidates and let the user
  // filter visually. Future: filter by /matricules?grup_id=...
  const alumnes: Alumne[] = useMemo(() => alumnesAll.data ?? [], [alumnesAll.data]);

  const [selected, setSelected] = useState<Set<number>>(new Set());
  useEffect(() => {
    setSelected(new Set());
  }, [grupId, avalId]);

  const toggle = (id: number) =>
    setSelected(prev => {
      const n = new Set(prev);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });

  const selectAll = () =>
    setSelected(prev =>
      prev.size === alumnes.length ? new Set() : new Set(alumnes.map(a => a.id)),
    );

  // --- options -----------------------------------------------------------

  const [opts, setOpts] = useState<ButlletiOpts>(DEFAULT_OPTS);
  const [lang, setLang] = useState<"ca" | "es">("ca"); // visual; backend currently renders ca only
  const [template, setTemplate] = useState<"A" | "B">("A");

  // --- preview -----------------------------------------------------------

  const previewAlumneId = useMemo(() => {
    const first = [...selected][0];
    return first ?? alumnes[0]?.id ?? null;
  }, [selected, alumnes]);

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (previewAlumneId === null || avalId === null) {
      setPreviewUrl(null);
      return;
    }
    let cancelled = false;
    let urlToRevoke: string | null = null;
    (async () => {
      try {
        const url = await outputsApi.previewUrl(previewAlumneId, avalId, accessToken);
        if (cancelled) {
          URL.revokeObjectURL(url);
        } else {
          urlToRevoke = url;
          setPreviewUrl(url);
        }
      } catch {
        if (!cancelled) setPreviewUrl(null);
      }
    })();
    return () => {
      cancelled = true;
      if (urlToRevoke) URL.revokeObjectURL(urlToRevoke);
    };
  }, [previewAlumneId, avalId, accessToken]);

  // --- mutations ---------------------------------------------------------

  const generateMut = useMutation({
    mutationFn: async () => {
      if (!avalId) throw new Error("no avaluacio");
      const ids = [...selected];
      if (ids.length === 0) throw new Error("selecciona almenys un alumne");
      return outputsApi.generateZip(avalId, ids, opts, accessToken);
    },
    onSuccess: ({ blob, filename, generated, failed }) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      if (failed === 0) {
        toast.success(`${generated} PDFs generats`);
      } else {
        toast.warn(`${generated} generats, ${failed} amb error`);
      }
    },
    onError: (err: Error) => toast.error(err.message || "Error en generar"),
  });

  const [confirmSend, setConfirmSend] = useState<"alumne" | "tutors" | "both" | null>(null);
  const sendMut = useMutation({
    mutationFn: async (sendTo: string[]) => {
      if (!avalId) throw new Error("no avaluacio");
      const ids = [...selected];
      if (ids.length === 0) throw new Error("selecciona almenys un alumne");
      return outputsApi.send(avalId, ids, sendTo, opts);
    },
    onSuccess: res => {
      if (res.failed === 0) {
        toast.success(`${res.sent} emails enviats`);
      } else {
        toast.warn(`${res.sent} enviats, ${res.failed} amb error`);
      }
    },
    onError: (err: ApiError) => toast.error(err.message || "Error en enviar"),
  });

  const aval = avals.data?.find(a => a.id === avalId) ?? null;
  const isTancada = aval?.estat === "tancada";

  // --- render ------------------------------------------------------------

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Sortides · Generació de butlletins</p>
        <h1 className={styles.title}>Butlletins</h1>
        <p className={styles.sub}>
          Genera PDFs per alumne i envia'ls per email. Recomanat amb l'avaluació en
          estat <em>tancada</em>; pots prèviament generar borradors en altres estats.
        </p>
      </header>

      <div className={styles.toolbar}>
        <Selector
          label="Curs"
          value={cursId}
          onChange={v => {
            setCursId(v);
            setAvalId(null);
            setGrupId(null);
          }}
          options={(cursos.data ?? []).map(c => ({ value: c.id, label: c.nom }))}
        />
        <Selector
          label="Grup"
          value={grupId}
          onChange={setGrupId}
          options={(grups.data ?? []).map(g => ({
            value: g.id,
            label: g.codi + (g.cicle_codi ? ` · ${g.cicle_codi}` : ""),
          }))}
        />
        <Selector
          label="Avaluació"
          value={avalId}
          onChange={setAvalId}
          options={(avals.data ?? []).map((a: Avaluacio) => ({
            value: a.id,
            label: `${a.nom} · ${a.estat}`,
          }))}
        />
        <span style={{ flex: 1 }} />
        <span className={styles.selCount}>
          {selected.size} de {alumnes.length} seleccionats
        </span>
        <Button
          disabled={selected.size === 0 || avalId === null || generateMut.isPending}
          onClick={() => generateMut.mutate()}
        >
          {generateMut.isPending ? "Generant…" : `Generar ${selected.size || ""} PDFs`}
        </Button>
        {(() => {
          // Send is admin-only OR tutor of the currently selected grup.
          const isTutorOfGrup =
            myAssigs.data?.tutorships?.includes(grupId ?? -1) ?? false;
          const canSend = isAdmin || isTutorOfGrup;
          if (!canSend) return null;
          return (
            <Button
              variant="primary"
              disabled={selected.size === 0 || avalId === null || sendMut.isPending}
              onClick={() => setConfirmSend("both")}
            >
              {sendMut.isPending ? "Enviant…" : "Enviar emails"}
            </Button>
          );
        })()}
      </div>

      {!isTancada && aval && (
        <div className={styles.banner}>
          L'avaluació actual està en estat <strong>{aval.estat}</strong>. Pots generar
          borradors, però els butlletins definitius es generen quan l'admin marca
          l'avaluació com a <em>tancada</em>.
        </div>
      )}

      <div className={styles.layout}>
        {/* Alumnes list */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>Alumnes</span>
            <Button size="sm" onClick={selectAll}>
              {selected.size === alumnes.length ? "Cap" : "Tots"}
            </Button>
          </div>
          <div className={styles.alumneList}>
            {alumnesAll.isLoading && <div className={styles.muted}>Carregant…</div>}
            {alumnes.map(a => {
              const isSel = selected.has(a.id);
              return (
                <button
                  key={a.id}
                  type="button"
                  className={`${styles.alumneRow} ${isSel ? styles.alumneSel : ""}`}
                  onClick={() => toggle(a.id)}
                >
                  <span className={`${styles.checkbox} ${isSel ? styles.checked : ""}`}>
                    {isSel && "✓"}
                  </span>
                  <span className={styles.alumneNom}>
                    {a.cognoms}, {a.nom}
                  </span>
                  <span className={styles.mono}>{a.dni ?? a.ralc}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Options */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>Configuració del PDF</span>
          </div>
          <div className={styles.optList}>
            <OptToggle
              label="Detall per RA"
              desc="Mostra cada RA amb la seva nota i pes"
              checked={opts.detall_ra}
              onChange={v => setOpts(o => ({ ...o, detall_ra: v }))}
            />
            <OptToggle
              label="Comentaris del professor"
              desc="Inclou els comentaris automàtics"
              checked={opts.comentaris}
              onChange={v => setOpts(o => ({ ...o, comentaris: v }))}
            />
            <OptToggle
              label="Distribució del grup"
              desc="Comparació amb el grup classe"
              checked={opts.distribucio_grup}
              onChange={v => setOpts(o => ({ ...o, distribucio_grup: v }))}
            />
            <OptToggle
              label="Signatura del tutor"
              desc="Camp per signatura digital"
              checked={opts.signatura}
              onChange={v => setOpts(o => ({ ...o, signatura: v }))}
            />
            <OptToggle
              label="Logo i capçalera"
              desc="Identitat visual del centre"
              checked={opts.logo_centre}
              onChange={v => setOpts(o => ({ ...o, logo_centre: v }))}
            />
          </div>
          <div className={styles.optFoot}>
            <span className={styles.optFootLabel}>Idioma · Plantilla</span>
            <div className={styles.chips}>
              <button
                type="button"
                className={`${styles.chip} ${lang === "ca" ? styles.chipActive : ""}`}
                onClick={() => setLang("ca")}
              >
                Català
              </button>
              <button
                type="button"
                className={`${styles.chip} ${lang === "es" ? styles.chipActive : ""}`}
                onClick={() => setLang("es")}
                disabled
                title="Plantilla castellana — Phase 4 follow-up"
              >
                Castellà
              </button>
              <span style={{ flex: 1 }} />
              <button
                type="button"
                className={`${styles.chip} ${styles.chipActive}`}
                onClick={() => setTemplate(template === "A" ? "B" : "A")}
              >
                Plantilla {template} · oficial
              </button>
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className={styles.card}>
          <div className={styles.cardHead}>
            <span>Previsualització</span>
            <span className={styles.mono}>
              {previewAlumneId
                ? alumnes.find(a => a.id === previewAlumneId)?.cognoms
                : "—"}
            </span>
          </div>
          <div className={styles.previewWrap}>
            {previewUrl ? (
              <iframe title="butlleti-preview" src={previewUrl} className={styles.iframe} />
            ) : (
              <div className={styles.muted}>
                {previewAlumneId === null
                  ? "Selecciona almenys un alumne per veure la previsualització."
                  : "Carregant PDF…"}
              </div>
            )}
          </div>
        </div>
      </div>

      {confirmSend && (
        <ConfirmDialog
          title="Enviar butlletins per email"
          message={`Enviaràs el butlletí de l'avaluació "${aval?.nom ?? ""}" als ${selected.size} alumnes seleccionats. Els emails s'enviaran a l'alumne i als tutors legals.`}
          detail="Aquesta acció no es pot desfer. Els emails es registren a la pestanya Enviaments per fer-ne seguiment."
          confirmLabel={`Enviar a ${selected.size} alumnes`}
          onConfirm={() => sendMut.mutateAsync(["alumne", "tutors"])}
          onClose={() => setConfirmSend(null)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function Selector({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: number | null;
  onChange: (v: number) => void;
  options: { value: number; label: string }[];
}) {
  return (
    <label className={styles.select}>
      <span>{label}</span>
      <select
        value={value ?? ""}
        onChange={e => onChange(Number(e.target.value))}
        disabled={options.length === 0}
      >
        {options.length === 0 && <option value="">—</option>}
        {options.map(o => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function OptToggle({
  label,
  desc,
  checked,
  onChange,
}: {
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className={styles.optRow}>
      <span className={`${styles.checkbox} ${checked ? styles.checked : ""}`}>
        {checked && "✓"}
      </span>
      <div className={styles.optBody}>
        <div className={styles.optLabel}>{label}</div>
        <div className={styles.optDesc}>{desc}</div>
      </div>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        style={{ display: "none" }}
      />
    </label>
  );
}
