/** Qualificacions page — grade spreadsheet with optimistic save + dirty tracking.
 *
 * Layout:
 *   [curs ▾] [grup ▾] [mòdul ▾] [avaluació ▾]   [N canvis] [Descartar] [Guardar]
 *   ┌─────────────────────────────────────────────────────────────────────────┐
 *   │ Alumne                  RA1   RA2   RA3   …   FINAL                      │
 *   │ Cognoms, nom            7.5   6.0   8.0       7.2                        │
 *   │ …                                                                        │
 *   └─────────────────────────────────────────────────────────────────────────┘
 *
 * Per cell: hover/focus reveals a "💬" button that opens a popup to add a
 * comentari per RA. The FINAL column is editable as a manual override that
 * bypasses the RA mean; empty means "use computed mean".
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { authApi } from "@/api/auth";
import { catalogApi, type CursAcademic, type Modul } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { exportsApi } from "@/api/exports";
import {
  gradingApi,
  type Avaluacio,
  type GradeMatrix,
  type QualifModulPatch,
  type QualifRaPatch,
} from "@/api/grading";
import { grupsApi, type Grup } from "@/api/grups";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Icon } from "@/components/ui/Icon";
import { useExport } from "@/hooks/useExport";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import { StatsPanel } from "./StatsPanel";
import styles from "./QualifsPage.module.css";

type RaEditValue = { nota: number | null; comentari: string | null };
type RaEditMap = Map<string, RaEditValue>; // key = `${matricula_id}:${ra_id}`
type ModulEditValue = { nota: number | null; comentari: string | null };
type ModulEditMap = Map<number, ModulEditValue>; // key = matricula_id

const raKey = (matriculaId: number, raId: number) => `${matriculaId}:${raId}`;

export function QualifsPage() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const urlCurs = searchParams.get("curs");
  const urlGrup = searchParams.get("grup");
  const urlModul = searchParams.get("modul");
  const userRole = useAuthStore(s => s.user?.role ?? null);
  const isAdmin = userRole === "admin";

  // --- selectors ---------------------------------------------------------

  const myAssigs = useQuery({
    queryKey: ["my-assignacions"],
    queryFn: () => authApi.myAssignacions(),
  });
  const accessibleGrupIds = useMemo(() => {
    if (!myAssigs.data || isAdmin) return null;
    return new Set<number>([
      ...myAssigs.data.assignacions.map(a => a.grup_id),
      ...myAssigs.data.tutorships,
    ]);
  }, [myAssigs.data, isAdmin]);
  const accessibleByGrup = useMemo(() => {
    if (!myAssigs.data || isAdmin) return null;
    const out = new Map<number, Set<number>>();
    for (const a of myAssigs.data.assignacions) {
      const s = out.get(a.grup_id) ?? new Set<number>();
      s.add(a.modul_id);
      out.set(a.grup_id, s);
    }
    return out;
  }, [myAssigs.data, isAdmin]);

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

  const filteredGrups = useMemo(() => {
    if (!grups.data) return [];
    if (accessibleGrupIds === null) return grups.data;
    return grups.data.filter(g => accessibleGrupIds.has(g.id));
  }, [grups.data, accessibleGrupIds]);

  const [grupId, setGrupId] = useState<number | null>(null);
  useEffect(() => {
    if (filteredGrups.length === 0) {
      if (grupId !== null) setGrupId(null);
      return;
    }
    if (grupId === null) {
      const target = urlGrup && filteredGrups.some(g => g.id === Number(urlGrup))
        ? Number(urlGrup)
        : filteredGrups[0]!.id;
      setGrupId(target);
      return;
    }
    if (!filteredGrups.some(g => g.id === grupId)) {
      setGrupId(filteredGrups[0]!.id);
    }
  }, [filteredGrups, grupId, urlGrup]);

  const grup = filteredGrups.find(g => g.id === grupId) ?? null;
  const moduls = useQuery({
    queryKey: ["moduls", grup?.cicle_id],
    queryFn: () => catalogApi.listModuls(grup!.cicle_id),
    enabled: grup !== null,
  });

  const filteredModuls = useMemo(() => {
    if (!moduls.data) return [];
    const sameCurs = grup ? moduls.data.filter(m => m.curs === grup.curs) : moduls.data;
    if (accessibleByGrup === null || grupId === null) return sameCurs;
    const allowedSet = accessibleByGrup.get(grupId);
    if (!allowedSet) return [];
    return sameCurs.filter(m => allowedSet.has(m.id));
  }, [moduls.data, accessibleByGrup, grupId, grup]);

  const [modulId, setModulId] = useState<number | null>(null);
  useEffect(() => {
    if (filteredModuls.length === 0) {
      if (modulId !== null) setModulId(null);
      return;
    }
    if (modulId === null) {
      const target =
        urlModul && filteredModuls.some(m => m.id === Number(urlModul))
          ? Number(urlModul)
          : filteredModuls[0]!.id;
      setModulId(target);
      return;
    }
    if (!filteredModuls.some(m => m.id === modulId)) {
      setModulId(filteredModuls[0]!.id);
    }
  }, [filteredModuls, modulId, urlModul]);

  const avals = useQuery({
    queryKey: ["avaluacions", cursId],
    queryFn: () => gradingApi.listAvaluacions(cursId ?? undefined),
    enabled: cursId !== null,
  });
  const [avalId, setAvalId] = useState<number | null>(null);
  useEffect(() => {
    if (avalId === null && avals.data && avals.data.length > 0) {
      const editable =
        avals.data.find(a => a.estat === "docent" || a.estat === "junta") ?? avals.data[0]!;
      setAvalId(editable.id);
    }
  }, [avalId, avals.data]);

  const allReady = grupId !== null && modulId !== null && avalId !== null;

  // --- matrix ------------------------------------------------------------

  const matrix = useQuery({
    queryKey: ["grade-matrix", grupId, modulId, avalId],
    queryFn: () =>
      gradingApi.getGradeMatrix({ grup_id: grupId!, modul_id: modulId!, avaluacio_id: avalId! }),
    enabled: allReady,
  });

  const [raEdits, setRaEdits] = useState<RaEditMap>(new Map());
  const [modulEdits, setModulEdits] = useState<ModulEditMap>(new Map());
  useEffect(() => {
    setRaEdits(new Map());
    setModulEdits(new Map());
  }, [grupId, modulId, avalId]);

  const raLookup = useMemo(() => {
    const m = new Map<string, RaEditValue>();
    matrix.data?.cells.forEach(c =>
      m.set(raKey(c.matricula_id, c.ra_id), { nota: c.nota, comentari: c.comentari }),
    );
    return m;
  }, [matrix.data]);

  const modulLookup = useMemo(() => {
    const m = new Map<number, ModulEditValue>();
    matrix.data?.modul_cells.forEach(c =>
      m.set(c.matricula_id, { nota: c.nota, comentari: c.comentari }),
    );
    return m;
  }, [matrix.data]);

  const dirtyCount = raEdits.size + modulEdits.size;

  const parseNota = (raw: string): number | null | "invalid" => {
    const trimmed = raw.trim();
    if (trimmed === "") return null;
    const parsed = Number.parseFloat(trimmed.replace(",", "."));
    if (Number.isNaN(parsed)) return "invalid";
    return Math.max(0, Math.min(10, Math.round(parsed * 100) / 100));
  };

  const setRaNota = (matriculaId: number, raId: number, raw: string) => {
    const next = parseNota(raw);
    if (next === "invalid") return;
    const orig = raLookup.get(raKey(matriculaId, raId)) ?? { nota: null, comentari: null };
    const k = raKey(matriculaId, raId);
    setRaEdits(prev => {
      const m = new Map(prev);
      const current = m.get(k) ?? orig;
      const merged: RaEditValue = { nota: next, comentari: current.comentari };
      if (merged.nota === orig.nota && merged.comentari === orig.comentari) m.delete(k);
      else m.set(k, merged);
      return m;
    });
  };

  const setRaComentari = (matriculaId: number, raId: number, comentari: string | null) => {
    const orig = raLookup.get(raKey(matriculaId, raId)) ?? { nota: null, comentari: null };
    const k = raKey(matriculaId, raId);
    const next: string | null = comentari?.trim() ? comentari.trim() : null;
    setRaEdits(prev => {
      const m = new Map(prev);
      const current = m.get(k) ?? orig;
      const merged: RaEditValue = { nota: current.nota, comentari: next };
      if (merged.nota === orig.nota && merged.comentari === orig.comentari) m.delete(k);
      else m.set(k, merged);
      return m;
    });
  };

  /** Bulk paste: parses TSV/CSV from clipboard into the matrix starting at
   * (startRowIdx, startColIdx). One row of clipboard = one alumne. One column
   * of clipboard = one RA (or the FINAL column at the end).
   *
   * Excel/Sheets put a tab-separated grid in the clipboard by default.
   * We also accept newline-separated single column (a column copied from Excel
   * pastes as values separated by \r\n). */
  const handleBulkPaste = (
    startRowIdx: number,
    startColIdx: number,
    text: string,
  ): { written: number; rejected: number } => {
    if (!matrix.data) return { written: 0, rejected: 0 };
    const lines = text.replace(/\r/g, "").split("\n").filter((l, i, arr) => !(i === arr.length - 1 && l === ""));
    if (lines.length === 0) return { written: 0, rejected: 0 };

    let written = 0;
    let rejected = 0;
    const ras = matrix.data.ras;
    const alumnes = matrix.data.alumnes;
    const FINAL_COL = ras.length; // virtual index for the FINAL column

    lines.forEach((line, dy) => {
      const cells = line.split("\t");
      const targetRow = startRowIdx + dy;
      if (targetRow >= alumnes.length) {
        rejected += cells.length;
        return;
      }
      const matriculaId = alumnes[targetRow]!.matricula_id;
      cells.forEach((raw, dx) => {
        const targetCol = startColIdx + dx;
        if (targetCol > FINAL_COL) {
          rejected += 1;
          return;
        }
        const parsed = parseNota(raw);
        if (parsed === "invalid") {
          if (raw.trim() !== "") rejected += 1;
          return;
        }
        if (targetCol === FINAL_COL) {
          // Final column → modul manual override
          setModulNotaRaw(matriculaId, parsed);
        } else {
          const raId = ras[targetCol]!.id;
          setRaNotaRaw(matriculaId, raId, parsed);
        }
        written += 1;
      });
    });
    return { written, rejected };
  };

  const setRaNotaRaw = (matriculaId: number, raId: number, next: number | null) => {
    const orig = raLookup.get(raKey(matriculaId, raId)) ?? { nota: null, comentari: null };
    const k = raKey(matriculaId, raId);
    setRaEdits(prev => {
      const m = new Map(prev);
      const current = m.get(k) ?? orig;
      const merged: RaEditValue = { nota: next, comentari: current.comentari };
      if (merged.nota === orig.nota && merged.comentari === orig.comentari) m.delete(k);
      else m.set(k, merged);
      return m;
    });
  };

  const setModulNotaRaw = (matriculaId: number, next: number | null) => {
    const orig = modulLookup.get(matriculaId) ?? { nota: null, comentari: null };
    setModulEdits(prev => {
      const m = new Map(prev);
      const current = m.get(matriculaId) ?? orig;
      const merged: ModulEditValue = { nota: next, comentari: current.comentari };
      if (merged.nota === orig.nota && merged.comentari === orig.comentari)
        m.delete(matriculaId);
      else m.set(matriculaId, merged);
      return m;
    });
  };

  const setModulNota = (matriculaId: number, raw: string) => {
    const next = parseNota(raw);
    if (next === "invalid") return;
    const orig = modulLookup.get(matriculaId) ?? { nota: null, comentari: null };
    setModulEdits(prev => {
      const m = new Map(prev);
      const current = m.get(matriculaId) ?? orig;
      const merged: ModulEditValue = { nota: next, comentari: current.comentari };
      if (merged.nota === orig.nota && merged.comentari === orig.comentari)
        m.delete(matriculaId);
      else m.set(matriculaId, merged);
      return m;
    });
  };

  const raCellValue = (matriculaId: number, raId: number): RaEditValue => {
    const k = raKey(matriculaId, raId);
    if (raEdits.has(k)) return raEdits.get(k)!;
    return raLookup.get(k) ?? { nota: null, comentari: null };
  };

  const modulCellValue = (matriculaId: number): ModulEditValue => {
    if (modulEdits.has(matriculaId)) return modulEdits.get(matriculaId)!;
    return modulLookup.get(matriculaId) ?? { nota: null, comentari: null };
  };

  const computedMean = (matriculaId: number): number | null => {
    if (!matrix.data) return null;
    let totalWeight = 0;
    let weighted = 0;
    for (const r of matrix.data.ras) {
      const v = raCellValue(matriculaId, r.id).nota;
      if (v === null) return null; // mean only meaningful when all RAs are graded
      const pes = Number.parseFloat(r.pes) || 0;
      totalWeight += pes;
      weighted += pes * v;
    }
    if (totalWeight === 0) return null;
    return Math.round((weighted / totalWeight) * 10) / 10;
  };

  const finalDisplay = (matriculaId: number): { value: number | null; manual: boolean } => {
    const manual = modulCellValue(matriculaId).nota;
    if (manual !== null) return { value: manual, manual: true };
    return { value: computedMean(matriculaId), manual: false };
  };

  // --- save --------------------------------------------------------------

  const saveRaMut = useMutation({
    mutationFn: (patches: QualifRaPatch[]) => gradingApi.batchPatch(avalId!, patches),
  });
  const saveModulMut = useMutation({
    mutationFn: (patches: QualifModulPatch[]) =>
      gradingApi.batchPatchModul(avalId!, modulId!, patches),
  });

  const isSaving = saveRaMut.isPending || saveModulMut.isPending;

  const handleSave = async () => {
    if (!matrix.data) return;
    const raPatches: QualifRaPatch[] = [];
    for (const [k, v] of raEdits) {
      const [matrId, raId] = k.split(":").map(Number);
      raPatches.push({
        matricula_id: matrId!,
        ra_id: raId!,
        nota: v.nota,
        comentari: v.comentari,
      });
    }
    const modulPatches: QualifModulPatch[] = [];
    for (const [matrId, v] of modulEdits) {
      modulPatches.push({ matricula_id: matrId, nota: v.nota, comentari: v.comentari });
    }

    try {
      let savedRa = 0;
      let savedModul = 0;
      const failed: { kind: string; error: string | null | undefined }[] = [];

      if (raPatches.length > 0) {
        const res = await saveRaMut.mutateAsync(raPatches);
        savedRa = res.saved;
        for (const r of res.results) if (!r.ok) failed.push({ kind: "ra", error: r.error });
      }
      if (modulPatches.length > 0) {
        const res = await saveModulMut.mutateAsync(modulPatches);
        savedModul = res.saved;
        for (const r of res.results) if (!r.ok) failed.push({ kind: "modul", error: r.error });
      }

      if (failed.length === 0) {
        toast.success(`${savedRa + savedModul} canvis desats`);
        setRaEdits(new Map());
        setModulEdits(new Map());
      } else {
        toast.warn(
          `${savedRa + savedModul} desats, ${failed.length} amb error (${failed[0]?.error ?? "?"})`,
        );
      }
      qc.invalidateQueries({ queryKey: ["grade-matrix", grupId, modulId, avalId] });
    } catch {
      toast.error("No s'han pogut desar tots els canvis");
    }
  };

  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const exporter = useExport();
  const [commentPopup, setCommentPopup] = useState<{
    matriculaId: number;
    raId: number;
    alumneLabel: string;
    raLabel: string;
  } | null>(null);

  // --- render ------------------------------------------------------------

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Qualificacions · Institut la Ferreria</p>
        <h1 className={styles.title}>Introducció de notes</h1>
        <p className={styles.sub}>
          Selecciona curs, grup, mòdul i avaluació. Notes per RA i, opcionalment,
          nota final manual que sobreescriu la mitjana ponderada.
        </p>
      </header>

      <div className={styles.toolbar}>
        <Selector
          label="Curs"
          value={cursId}
          onChange={setCursId}
          options={(cursos.data ?? []).map(c => ({
            value: c.id,
            label: c.nom + (c.actiu ? " · actiu" : ""),
          }))}
        />
        <Selector
          label="Grup"
          value={grupId}
          onChange={setGrupId}
          options={filteredGrups.map((g: Grup) => ({
            value: g.id,
            label: g.codi + (g.cicle_codi ? ` · ${g.cicle_codi}` : ""),
          }))}
        />
        <Selector
          label="Mòdul"
          value={modulId}
          onChange={setModulId}
          options={filteredModuls.map((m: Modul) => ({
            value: m.id,
            label: `${m.codi} · ${m.nom}`,
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

        {dirtyCount > 0 && (
          <span className={styles.dirty}>{dirtyCount} canvis sense guardar</span>
        )}
        <Button disabled={dirtyCount === 0 || isSaving} onClick={() => setConfirmDiscard(true)}>
          Descartar
        </Button>
        <Button
          variant="primary"
          disabled={dirtyCount === 0 || isSaving || !matrix.data?.can_edit}
          onClick={handleSave}
        >
          {isSaving ? "Desant…" : `Guardar ${dirtyCount > 0 ? `(${dirtyCount})` : ""}`}
        </Button>
        <Button
          disabled={!allReady}
          onClick={() => setShowStats(s => !s)}
          title={showStats ? "Amagar estadístiques" : "Veure estadístiques"}
        >
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <Icon name="chart" size={14} />
            {showStats ? "Amagar estadístiques" : "Estadístiques"}
          </span>
        </Button>
        <Button
          disabled={!allReady || exporter.exporting}
          onClick={() =>
            exporter.run(
              t => exportsApi.grupModul(grupId!, modulId!, avalId, t),
              "Qualificacions",
            )
          }
        >
          {exporter.exporting ? "Exportant…" : "⬇ Exportar"}
        </Button>
      </div>

      {showStats && allReady && (
        <StatsPanel grupId={grupId!} modulId={modulId!} avaluacioId={avalId!} />
      )}

      {!isAdmin && accessibleGrupIds && accessibleGrupIds.size === 0 && (
        <div className={styles.banner}>
          <strong>Cap assignació docent.</strong> El teu compte no té cap grup
          ni mòdul assignat aquest curs. Demana a l'admin que t'afegeixi una
          assignació a <em>Configuració</em>.
        </div>
      )}

      {!isAdmin && filteredGrups.length > 0 && filteredModuls.length === 0 && grup && (
        <div className={styles.banner}>
          <strong>Sense mòduls disponibles per a aquest grup.</strong> Estàs
          tutor de <em>{grup.codi}</em> però no tens cap mòdul d'aquest grup
          assignat. Pots editar quan l'avaluació estigui en <em>junta</em>.
        </div>
      )}

      {matrix.isError && (
        <div className={styles.banner}>
          <strong>No s'ha pogut carregar la matriu.</strong>{" "}
          {(matrix.error as ApiError | undefined)?.code === "permission_denied"
            ? "No tens permís per veure aquesta combinació de grup i mòdul."
            : (matrix.error as ApiError | undefined)?.message ??
              "Error desconegut. Mira la consola del navegador."}
        </div>
      )}

      {matrix.data && !matrix.data.can_edit && (
        <div className={styles.banner}>
          <strong>Mode lectura.</strong> No tens permís per editar en l'estat{" "}
          <em>{matrix.data.avaluacio_estat}</em>. {permissionHint(matrix.data)}
        </div>
      )}

      <section className={styles.spreadsheet}>
        {!allReady && (
          <p className={styles.muted}>Selecciona grup, mòdul i avaluació per començar.</p>
        )}
        {matrix.isLoading && allReady && <p className={styles.muted}>Carregant matriu…</p>}
        {matrix.data && matrix.data.alumnes.length === 0 && (
          <p className={styles.muted}>Aquest grup encara no té alumnes matriculats.</p>
        )}
        {matrix.data && matrix.data.ras.length === 0 && (
          <p className={styles.muted}>Aquest mòdul encara no té RAs definits.</p>
        )}

        {matrix.data && matrix.data.ras.length > 0 && (() => {
          const totalPes = matrix.data.ras.reduce(
            (acc, r) => acc + (Number.parseFloat(r.pes) || 0),
            0,
          );
          if (Math.abs(totalPes - 100) < 0.01) return null;
          return (
            <div className={styles.banner}>
              <strong>⚠ Pesos del mòdul sumen {totalPes.toFixed(2)}%, no 100%.</strong>{" "}
              El càlcul de la nota final es normalitza igualment, però convé revisar
              els pesos a <em>Currículums</em>.
            </div>
          );
        })()}

        {matrix.data && matrix.data.alumnes.length > 0 && matrix.data.ras.length > 0 && (
          <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.colAlumne}>Alumne</th>
                  {matrix.data.ras.map(r => (
                    <th key={r.id} className={styles.colRa} title={r.descripcio}>
                      <span className={styles.raCodi}>{r.codi}</span>
                      <span className={styles.raPes}>{r.pes}%</span>
                    </th>
                  ))}
                  <th className={styles.colFinal} title="Nota final del mòdul (manual o mitjana ponderada)">
                    FINAL
                  </th>
                </tr>
              </thead>
              <tbody>
                {matrix.data.alumnes.map((a, rowIdx) => {
                  const fin = finalDisplay(a.matricula_id);
                  const modulCellEdited = modulEdits.has(a.matricula_id);
                  return (
                    <tr key={a.matricula_id}>
                      <td className={styles.alumneCell}>
                        <div className={styles.alumneNom}>
                          {a.cognoms}, {a.nom}
                        </div>
                        <div className={styles.alumneId}>{a.dni ?? a.ralc}</div>
                      </td>
                      {matrix.data!.ras.map((r, colIdx) => {
                        const k = raKey(a.matricula_id, r.id);
                        const dirty = raEdits.has(k);
                        const cell = raCellValue(a.matricula_id, r.id);
                        const hasComment = cell.comentari && cell.comentari.length > 0;
                        return (
                          <td key={r.id} className={styles.cellTd}>
                            <div className={styles.cellWrap}>
                              <input
                                className={`${styles.cell} ${classForNota(cell.nota)} ${
                                  dirty ? styles.dirtyCell : ""
                                }`}
                                value={cell.nota === null ? "" : String(cell.nota)}
                                placeholder="—"
                                disabled={!matrix.data!.can_edit}
                                onChange={e =>
                                  setRaNota(a.matricula_id, r.id, e.target.value)
                                }
                                onPaste={e => {
                                  const text = e.clipboardData.getData("text/plain");
                                  if (!text || (!text.includes("\t") && !text.includes("\n"))) return;
                                  e.preventDefault();
                                  const res = handleBulkPaste(rowIdx, colIdx, text);
                                  if (res.written > 0) {
                                    toast.success(
                                      `${res.written} notes enganxades` +
                                        (res.rejected > 0
                                          ? ` (${res.rejected} cel·les rebutjades)`
                                          : ""),
                                    );
                                  } else if (res.rejected > 0) {
                                    toast.warn(
                                      `Cap nota vàlida — ${res.rejected} cel·les rebutjades`,
                                    );
                                  }
                                }}
                              />
                              <button
                                type="button"
                                className={`${styles.commentBtn} ${hasComment ? styles.commentBtnActive : ""}`}
                                onClick={() =>
                                  setCommentPopup({
                                    matriculaId: a.matricula_id,
                                    raId: r.id,
                                    alumneLabel: `${a.cognoms}, ${a.nom}`,
                                    raLabel: r.codi,
                                  })
                                }
                                title={
                                  hasComment
                                    ? `Comentari: ${cell.comentari}`
                                    : "Afegir comentari"
                                }
                              >
                                {hasComment ? "💬" : "+"}
                              </button>
                            </div>
                          </td>
                        );
                      })}
                      <td className={styles.finalCell}>
                        {(() => {
                          const mv = modulCellValue(a.matricula_id).nota;
                          const auto = computedMean(a.matricula_id);
                          return (
                            <input
                              className={`${styles.cell} ${styles.finalInput} ${classForNota(
                                fin.value,
                              )} ${modulCellEdited ? styles.dirtyCell : ""} ${
                                fin.manual ? styles.finalManual : styles.finalAuto
                              }`}
                              value={mv === null ? "" : String(mv)}
                              placeholder={auto === null ? "—" : `${auto.toFixed(1)} (auto)`}
                              disabled={!matrix.data!.can_edit}
                              onChange={e => setModulNota(a.matricula_id, e.target.value)}
                              onPaste={e => {
                                const text = e.clipboardData.getData("text/plain");
                                if (!text || (!text.includes("\t") && !text.includes("\n"))) return;
                                e.preventDefault();
                                const res = handleBulkPaste(
                                  rowIdx,
                                  matrix.data!.ras.length, // FINAL column
                                  text,
                                );
                                if (res.written > 0) {
                                  toast.success(`${res.written} notes finals enganxades`);
                                }
                              }}
                              title={
                                fin.manual
                                  ? "Nota final manual (sobreescriu la mitjana)"
                                  : "Mitjana ponderada — escriu un valor per sobreescriure"
                              }
                            />
                          );
                        })()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {matrix.data && (
        <p className={styles.statusFoot}>
          Estat: <strong>{matrix.data.avaluacio_estat}</strong> ·{" "}
          {matrix.data.alumnes.length} alumnes · {matrix.data.ras.length} RA ·{" "}
          <span title="Pots copiar un rang d'Excel i enganxar-lo directament a la graella">
            📋 paste des d'Excel suportat
          </span>{" "}·{" "}
          <span className={styles.legend}>
            <span className={styles.legendDot} style={{ background: "var(--accent)" }} />
            manual
          </span>{" "}
          <span className={styles.legend}>
            <span className={styles.legendDot} style={{ background: "var(--line)" }} />
            auto (mitjana ponderada)
          </span>
        </p>
      )}

      {confirmDiscard && (
        <ConfirmDialog
          title="Descartar canvis"
          message={`Tens ${dirtyCount} canvis sense guardar. Descartar-los no es pot desfer.`}
          confirmLabel="Descartar"
          variant="danger"
          onConfirm={() => {
            setRaEdits(new Map());
            setModulEdits(new Map());
          }}
          onClose={() => setConfirmDiscard(false)}
        />
      )}

      {commentPopup && (
        <CommentEditor
          alumneLabel={commentPopup.alumneLabel}
          raLabel={commentPopup.raLabel}
          initial={raCellValue(commentPopup.matriculaId, commentPopup.raId).comentari ?? ""}
          onClose={() => setCommentPopup(null)}
          onSave={text => {
            setRaComentari(commentPopup.matriculaId, commentPopup.raId, text);
            setCommentPopup(null);
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function classForNota(n: number | null): string {
  if (n === null) return styles.cellEmpty!;
  if (n < 5) return styles.cellSusp!;
  if (n >= 9) return styles.cellExc!;
  return styles.cellApr!;
}

function permissionHint(matrix: GradeMatrix): string {
  if (matrix.avaluacio_estat === "tancada") return "L'avaluació està tancada.";
  if (matrix.avaluacio_estat === "oberta") return "L'admin encara no ha obert el període docent.";
  if (matrix.avaluacio_estat === "docent")
    return "Només els professors assignats al mòdul poden editar en aquest estat.";
  if (matrix.avaluacio_estat === "junta")
    return "Només el tutor del grup pot editar en aquest estat.";
  return "";
}

function Selector<T extends number | null>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
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

export function CommentEditor({
  alumneLabel,
  raLabel,
  initial,
  onClose,
  onSave,
}: {
  alumneLabel: string;
  raLabel: string;
  initial: string;
  onClose: () => void;
  onSave: (text: string) => void;
}) {
  const [text, setText] = useState(initial);
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    ref.current?.focus();
    ref.current?.setSelectionRange(text.length, text.length);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={styles.commentBackdrop} onClick={onClose}>
      <div className={styles.commentPopup} onClick={e => e.stopPropagation()}>
        <header className={styles.commentHead}>
          <span className={styles.commentEyebrow}>Comentari · {raLabel}</span>
          <strong>{alumneLabel}</strong>
        </header>
        <textarea
          ref={ref}
          className={styles.commentTextarea}
          value={text}
          rows={5}
          maxLength={2000}
          onChange={e => setText(e.target.value)}
          placeholder="Observacions, lliuraments pendents, motiu de la nota…"
        />
        <footer className={styles.commentFoot}>
          <span className={styles.commentCount}>{text.length} / 2000</span>
          <span style={{ flex: 1 }} />
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button variant="primary" onClick={() => onSave(text)}>
            Aplicar
          </Button>
        </footer>
      </div>
    </div>
  );
}
