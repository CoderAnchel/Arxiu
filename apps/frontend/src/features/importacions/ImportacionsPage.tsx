/** Importacions — drag-and-drop CSV/XLSX upload with preview + confirm + history.
 *
 * Alumnes + Notes importers both wired end-to-end. Matrícules importer follows
 * the same backend pattern but is not yet wired.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { authApi } from "@/api/auth";
import { catalogApi, type Modul } from "@/api/catalog";
import { gradingApi, type Avaluacio } from "@/api/grading";
import {
  importsApi,
  type ImportPreview,
  type TipusImport,
} from "@/api/imports";
import { Button } from "@/components/ui/Button";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./ImportacionsPage.module.css";

const TIPUS_INFO: Record<
  TipusImport,
  { label: string; desc: string; cols: string[]; templateRows: (string | number)[][] }
> = {
  alumnes: {
    label: "Alumnes",
    desc: "Crea o actualitza fitxes d'alumnes des d'un Excel/CSV.",
    cols: ["ralc", "dni", "nom", "cognoms", "email", "telefon", "data_naixement", "tutor_email"],
    templateRows: [
      ["R0000001", "11111111H", "Aleix", "Vilanova", "aleix.v@alumnes.cat", "600000001", "2007-03-12", "tutor1@gmail.com"],
      ["R0000002", "22222222J", "Berta", "Puigdomènech", "berta.p@alumnes.cat", "", "2007-06-04", "tutor2@gmail.com"],
    ],
  },
  matricules: {
    label: "Matrícules",
    desc: "Assigna alumnes existents a grups classe per al curs seleccionat.",
    cols: ["ralc", "grup", "cicle", "curs", "estat"],
    templateRows: [
      ["R0000001", "DAM1A", "DAM", 1, "actiu"],
      ["R0000002", "SMX1A", "SMX", 1, "actiu"],
    ],
  },
  notes: {
    label: "Notes",
    desc: "Carrega qualificacions per RA d'un mòdul concret.",
    cols: ["dni_or_ralc", "nom", "RA1", "RA2", "RA3", "RA4"],
    templateRows: [
      ["11111111H", "Aleix Vilanova", 7.5, 6.0, 8.0, 7.0],
      ["22222222J", "Berta Puigdomènech", 9.0, 8.5, 9.5, 9.0],
    ],
  },
};

function downloadTemplate(tipus: TipusImport) {
  const info = TIPUS_INFO[tipus];
  const rows = [info.cols, ...info.templateRows];
  // Quote any cell containing comma/quote/newline; double internal quotes.
  const csv = rows
    .map(row =>
      row
        .map(cell => {
          const s = String(cell);
          if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
          return s;
        })
        .join(","),
    )
    .join("\r\n");
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `plantilla_${tipus}.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function ImportacionsPage() {
  const qc = useQueryClient();
  const accessToken = useAuthStore(s => s.accessToken);
  const user = useAuthStore(s => s.user);
  const isAdmin = user?.role === "admin";

  const [tipus, setTipus] = useState<TipusImport>("alumnes");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // Curs selector — applies to notes and matricules; alumnes are curs-agnostic.
  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const [cursId, setCursId] = useState<number | null>(null);
  useEffect(() => {
    if (cursId !== null) return;
    const actiu = cursos.data?.find(c => c.actiu) ?? cursos.data?.[0];
    if (actiu) setCursId(actiu.id);
  }, [cursId, cursos.data]);

  // For "notes" import we need to know the (mòdul, avaluació) before uploading
  const [modulId, setModulId] = useState<number | null>(null);
  const [avalId, setAvalId] = useState<number | null>(null);

  const myAssigs = useQuery({
    queryKey: ["my-assignacions"],
    queryFn: () => authApi.myAssignacions(),
    enabled: tipus === "notes" && !isAdmin,
  });

  const moduls = useQuery({
    queryKey: ["moduls-all"],
    queryFn: () => catalogApi.listModuls(),
    enabled: tipus === "notes",
  });

  // Filter the modul dropdown by what the professor is assigned to in the
  // selected curs. Admins see everything.
  const accessibleModulIds = useMemo(() => {
    if (isAdmin || !myAssigs.data || cursId === null) return null;
    return new Set(
      myAssigs.data.assignacions
        .filter(a => a.curs_acad_id === cursId)
        .map(a => a.modul_id),
    );
  }, [isAdmin, myAssigs.data, cursId]);

  const filteredModuls = useMemo(() => {
    if (!moduls.data) return [];
    if (accessibleModulIds === null) return moduls.data;
    return moduls.data.filter(m => accessibleModulIds.has(m.id));
  }, [moduls.data, accessibleModulIds]);

  const avals = useQuery({
    queryKey: ["avaluacions", cursId],
    queryFn: () => gradingApi.listAvaluacions(cursId ?? undefined),
    enabled: tipus === "notes" && cursId !== null,
  });

  useEffect(() => {
    if (tipus !== "notes") {
      setModulId(null);
      setAvalId(null);
    }
  }, [tipus]);

  // Reset modul/aval when curs changes — they only make sense for one curs
  useEffect(() => {
    setModulId(null);
    setAvalId(null);
  }, [cursId]);

  const history = useQuery({
    queryKey: ["imports"],
    queryFn: () => importsApi.list(),
  });

  const uploadMut = useMutation({
    mutationFn: (file: File) => {
      if (tipus === "alumnes") {
        return importsApi.uploadAlumnes(file, accessToken);
      }
      if (tipus === "notes") {
        if (modulId === null || avalId === null) {
          throw new Error("Selecciona mòdul i avaluació abans de pujar el fitxer.");
        }
        return importsApi.uploadNotes(file, modulId, avalId, accessToken);
      }
      throw new Error("Aquest importador no està disponible encara.");
    },
    onSuccess: data => {
      setPreview(data);
      toast.success(`Fitxer parsejat — ${data.ok} files vàlides, ${data.errors} amb errors`);
      qc.invalidateQueries({ queryKey: ["imports"] });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const confirmMut = useMutation({
    mutationFn: (id: number) => importsApi.confirm(id),
    onSuccess: result => {
      if (result.result) {
        const { created, updated, errors } = result.result;
        if (errors === 0) {
          toast.success(`Importació completada · ${created} creats · ${updated} actualitzats`);
        } else {
          toast.warn(
            `Completada amb errors · ${created} creats · ${updated} actualitzats · ${errors} fallits`,
          );
        }
      }
      setPreview(null);
      qc.invalidateQueries({ queryKey: ["imports"] });
      qc.invalidateQueries({ queryKey: ["alumnes"] });
    },
    onError: () => toast.error("La confirmació ha fallat"),
  });

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const file = files[0]!;
    if (file.size > 5 * 1024 * 1024) {
      toast.error("Fitxer massa gran (límit 5 MB)");
      return;
    }
    uploadMut.mutate(file);
  };

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Entrades de dades · Excel / CSV</p>
        <h1 className={styles.title}>Importacions</h1>
        <p className={styles.sub}>
          Carrega fitxers per crear alumnes, matrícules i qualificacions massivament.
          Cada importació es valida abans de confirmar i queda registrada.
        </p>
      </header>

      <div className={styles.tipusRow}>
        {(Object.keys(TIPUS_INFO) as TipusImport[]).map(t => (
          <button
            key={t}
            type="button"
            className={`${styles.tipusCard} ${tipus === t ? styles.tipusActive : ""}`}
            onClick={() => {
              setTipus(t);
              setPreview(null);
            }}
            disabled={t === "matricules"}
            title={t === "matricules" ? "Importador disponible properament" : undefined}
          >
            <strong>{TIPUS_INFO[t].label}</strong>
            <span>{TIPUS_INFO[t].desc}</span>
            {t === "matricules" && <span className={styles.soonBadge}>aviat</span>}
          </button>
        ))}
      </div>

      <div className={styles.contextRow}>
        {(tipus === "notes" || tipus === "matricules") && (
          <label className={styles.select}>
            <span>Curs acadèmic</span>
            <select
              value={cursId ?? ""}
              onChange={e => setCursId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— selecciona —</option>
              {(cursos.data ?? []).map(c => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                  {c.actiu ? " · actiu" : ""}
                </option>
              ))}
            </select>
          </label>
        )}
        <span style={{ flex: 1 }} />
        <Button onClick={() => downloadTemplate(tipus)}>
          ⬇ Descarregar plantilla {TIPUS_INFO[tipus].label.toLowerCase()}
        </Button>
      </div>

      {tipus === "notes" && !preview && (
        <div className={styles.notesSelectors}>
          <label className={styles.select}>
            <span>Mòdul</span>
            <select
              value={modulId ?? ""}
              onChange={e => setModulId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— selecciona —</option>
              {filteredModuls.map((m: Modul) => (
                <option key={m.id} value={m.id}>
                  {m.codi} · {m.nom}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.select}>
            <span>Avaluació</span>
            <select
              value={avalId ?? ""}
              onChange={e => setAvalId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— selecciona —</option>
              {avals.data?.map((a: Avaluacio) => (
                <option key={a.id} value={a.id}>
                  {a.nom} · {a.estat}
                </option>
              ))}
            </select>
          </label>
          {(modulId === null || avalId === null) && (
            <p className={styles.notesHint}>
              Selecciona mòdul i avaluació abans de pujar el fitxer de notes.
            </p>
          )}
        </div>
      )}

      {!preview && (
        <div
          className={`${styles.dropzone} ${dragOver ? styles.dropzoneOver : ""} ${
            tipus === "notes" && (modulId === null || avalId === null) ? styles.dropzoneDisabled : ""
          }`}
          onDragOver={e => {
            e.preventDefault();
            if (tipus === "notes" && (modulId === null || avalId === null)) return;
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => {
            e.preventDefault();
            setDragOver(false);
            if (tipus === "notes" && (modulId === null || avalId === null)) return;
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => {
            if (tipus === "notes" && (modulId === null || avalId === null)) {
              toast.warn("Selecciona mòdul i avaluació abans");
              return;
            }
            fileInput.current?.click();
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.xlsx,.xlsm,.tsv"
            style={{ display: "none" }}
            onChange={e => handleFiles(e.target.files)}
          />
          <div className={styles.dropIcon}>⬇</div>
          <div className={styles.dropBig}>
            {uploadMut.isPending ? "Pujant…" : "Arrossega el fitxer aquí"}
          </div>
          <div className={styles.dropSub}>
            o fes clic per seleccionar · accepta .xlsx, .csv · max 5 MB · UTF-8
          </div>

          <div className={styles.expected}>
            <div className={styles.expectedLabel}>Columnes esperades</div>
            <div className={styles.expectedList}>
              {TIPUS_INFO[tipus].cols.map(c => (
                <span key={c} className={styles.colTag}>
                  {c}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {preview && (
        <div className={styles.previewCard}>
          <div className={styles.previewHead}>
            <div>
              <div className={styles.previewFile}>{preview.fitxer_nom}</div>
              <div className={styles.previewMeta}>
                {preview.total} files · {preview.ok} vàlides ·{" "}
                {preview.errors > 0 ? (
                  <span className={styles.errorsLabel}>{preview.errors} amb errors</span>
                ) : (
                  <span className={styles.okLabel}>0 errors</span>
                )}
              </div>
            </div>
            <div className={styles.previewActions}>
              <Button onClick={() => setPreview(null)}>← Canviar fitxer</Button>
              <Button
                variant="primary"
                disabled={preview.ok === 0 || confirmMut.isPending}
                onClick={() => confirmMut.mutate(preview.id)}
              >
                {confirmMut.isPending
                  ? "Confirmant…"
                  : `Confirmar i importar ${preview.ok} files`}
              </Button>
            </div>
          </div>

          <div className={styles.previewTableWrap}>
            <table className={styles.previewTable}>
              <thead>
                <tr>
                  <th>#</th>
                  <th>RALC</th>
                  <th>Nom</th>
                  <th>Cognoms</th>
                  <th>DNI</th>
                  <th>Email</th>
                  <th>Estat</th>
                </tr>
              </thead>
              <tbody>
                {preview.preview.slice(0, 50).map(row => (
                  <tr
                    key={row.row}
                    className={
                      row.errors.length > 0
                        ? styles.rowErr
                        : row.warnings.length > 0
                          ? styles.rowWarn
                          : ""
                    }
                  >
                    <td className={styles.mono}>{row.row}</td>
                    <td className={styles.mono}>{String(row.data.ralc ?? "")}</td>
                    <td>{String(row.data.nom ?? "")}</td>
                    <td>{String(row.data.cognoms ?? "")}</td>
                    <td className={styles.mono}>{String(row.data.dni ?? "—")}</td>
                    <td>{String(row.data.email ?? "—")}</td>
                    <td>
                      {row.errors.length > 0 ? (
                        <span className={styles.errBadge} title={row.errors.join("; ")}>
                          {row.errors[0]}
                        </span>
                      ) : row.warnings.length > 0 ? (
                        <span className={styles.warnBadge} title={row.warnings.join("; ")}>
                          {row.warnings[0]}
                        </span>
                      ) : (
                        <span className={styles.okBadge}>ok</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {preview.preview.length > 50 && (
            <p className={styles.muted}>
              Mostrant les primeres 50 files. La resta es processa igualment en confirmar.
            </p>
          )}
        </div>
      )}

      {/* History */}
      <div className={styles.historyCard}>
        <div className={styles.historyHead}>
          <h2>Historial d'importacions</h2>
          <span className={styles.muted}>
            {history.data?.length ?? 0} entrades
          </span>
        </div>
        {history.isLoading && <p className={styles.muted}>Carregant…</p>}
        {history.data && history.data.length === 0 && (
          <p className={styles.muted}>Encara no s'ha importat cap fitxer.</p>
        )}
        {history.data && history.data.length > 0 && (
          <table className={styles.previewTable}>
            <thead>
              <tr>
                <th>Data</th>
                <th>Tipus</th>
                <th>Fitxer</th>
                <th>Total</th>
                <th>OK</th>
                <th>Errors</th>
                <th>Estat</th>
              </tr>
            </thead>
            <tbody>
              {history.data.map(h => (
                <tr key={h.id}>
                  <td className={styles.mono}>
                    {new Date(h.created_at).toLocaleString("ca-ES", {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td>
                    <span className={styles.tag}>{h.tipus}</span>
                  </td>
                  <td>{h.fitxer_nom}</td>
                  <td className={styles.mono}>{h.total}</td>
                  <td className={styles.mono}>{h.ok}</td>
                  <td className={styles.mono}>{h.errors}</td>
                  <td>
                    <span className={`${styles.estatTag} ${styles[`estat_${h.estat}`]}`}>
                      {h.estat}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
