/** Global Cmd+K palette — searches alumnes / grups / cicles and navigates.
 *
 * Opens with ⌘K / Ctrl+K from anywhere inside AppShell. The trigger lives in
 * the Topbar as well. Arrow keys to navigate, Enter to select, Esc to close.
 */
import { useQuery } from "@tanstack/react-query";
import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { catalogApi, type Cicle } from "@/api/catalog";
import { grupsApi, type Grup } from "@/api/grups";
import { peopleApi, type Alumne } from "@/api/people";

import styles from "./CmdK.module.css";

type Result =
  | { kind: "alumne"; alumne: Alumne }
  | { kind: "grup"; grup: Grup }
  | { kind: "cicle"; cicle: Cicle }
  | { kind: "shortcut"; label: string; to: string; hint?: string };

const SHORTCUTS: Result[] = [
  { kind: "shortcut", label: "Anar a l'Arxiu", to: "/", hint: "dashboard" },
  { kind: "shortcut", label: "Qualificacions", to: "/qualificacions", hint: "notes" },
  { kind: "shortcut", label: "Avaluacions", to: "/avaluacions", hint: "estats" },
  { kind: "shortcut", label: "Alumnes", to: "/alumnes" },
  { kind: "shortcut", label: "Currículums", to: "/curriculums" },
  { kind: "shortcut", label: "Docents", to: "/docents" },
  { kind: "shortcut", label: "Butlletins", to: "/butlletins" },
  { kind: "shortcut", label: "Enviaments", to: "/enviaments" },
  { kind: "shortcut", label: "Importacions", to: "/importacions" },
  { kind: "shortcut", label: "Auditoria", to: "/audit", hint: "admin" },
];

export function CmdK({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const dq = useDeferredValue(q);
  const [activeIdx, setActiveIdx] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  // Search results
  const trimmed = dq.trim();
  const alumnesQ = useQuery({
    queryKey: ["cmdk-alumnes", trimmed],
    queryFn: () => peopleApi.listAlumnes({ q: trimmed, limit: 8 }),
    enabled: open && trimmed.length >= 2,
  });
  const grupsQ = useQuery({
    queryKey: ["cmdk-grups"],
    queryFn: () => grupsApi.list(),
    enabled: open,
  });
  const ciclesQ = useQuery({
    queryKey: ["cmdk-cicles"],
    queryFn: () => catalogApi.listCicles(),
    enabled: open,
  });

  const results: Result[] = useMemo(() => {
    const ql = trimmed.toLowerCase();
    const filterText = (s: string) => !ql || s.toLowerCase().includes(ql);
    const out: Result[] = [];

    if (alumnesQ.data && trimmed.length >= 2) {
      for (const a of alumnesQ.data.slice(0, 6)) {
        out.push({ kind: "alumne", alumne: a });
      }
    }

    for (const g of (grupsQ.data ?? []).filter(g => filterText(`${g.codi} ${g.cicle_codi ?? ""}`))) {
      if (out.length >= 14) break;
      out.push({ kind: "grup", grup: g });
    }

    for (const c of (ciclesQ.data ?? []).filter(c =>
      filterText(`${c.codi} ${c.nom}`),
    )) {
      if (out.length >= 18) break;
      out.push({ kind: "cicle", cicle: c });
    }

    for (const s of SHORTCUTS.filter(s =>
      s.kind === "shortcut" ? filterText(s.label) : true,
    )) {
      if (out.length >= 24) break;
      out.push(s);
    }

    return out;
  }, [alumnesQ.data, grupsQ.data, ciclesQ.data, trimmed]);

  const choose = useCallback(
    (r: Result) => {
      onClose();
      switch (r.kind) {
        case "alumne":
          navigate(`/alumnes?selected=${r.alumne.id}`);
          break;
        case "grup":
          navigate(`/qualificacions?grup=${r.grup.id}`);
          break;
        case "cicle":
          navigate(`/curriculums?cicle=${r.cicle.id}`);
          break;
        case "shortcut":
          navigate(r.to);
          break;
      }
    },
    [navigate, onClose],
  );

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx(i => Math.min(i + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx(i => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        if (results[activeIdx]) {
          e.preventDefault();
          choose(results[activeIdx]!);
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, results, activeIdx, choose, onClose]);

  useEffect(() => {
    setActiveIdx(0);
  }, [dq]);

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onClose} role="presentation">
      <div className={styles.box} onClick={e => e.stopPropagation()} role="dialog">
        <input
          ref={inputRef}
          className={styles.input}
          placeholder="Cerca alumnes, grups, cicles o pàgines…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
        <div className={styles.list}>
          {results.length === 0 && (
            <div className={styles.muted}>
              {trimmed.length === 0
                ? "Escriu per cercar — o navega per les dreceres"
                : "Cap resultat"}
            </div>
          )}
          {results.map((r, idx) => (
            <button
              key={resultKey(r, idx)}
              type="button"
              className={`${styles.row} ${idx === activeIdx ? styles.active : ""}`}
              onMouseEnter={() => setActiveIdx(idx)}
              onClick={() => choose(r)}
            >
              <ResultRow result={r} />
            </button>
          ))}
        </div>
        <div className={styles.foot}>
          <span>
            <kbd>↑↓</kbd> moure · <kbd>↵</kbd> obrir · <kbd>esc</kbd> tancar
          </span>
          <span className={styles.foothint}>⌘K obre aquesta cerca</span>
        </div>
      </div>
    </div>
  );
}

function resultKey(r: Result, idx: number): string {
  switch (r.kind) {
    case "alumne": return `alumne-${r.alumne.id}`;
    case "grup": return `grup-${r.grup.id}`;
    case "cicle": return `cicle-${r.cicle.id}`;
    case "shortcut": return `s-${r.to}-${idx}`;
  }
}

function ResultRow({ result }: { result: Result }) {
  switch (result.kind) {
    case "alumne":
      return (
        <>
          <span className={styles.kindTag}>alumne</span>
          <span className={styles.label}>
            {result.alumne.cognoms}, {result.alumne.nom}
          </span>
          <span className={styles.mono}>
            {result.alumne.dni ?? result.alumne.ralc}
          </span>
        </>
      );
    case "grup":
      return (
        <>
          <span className={styles.kindTag}>grup</span>
          <span className={styles.label}>{result.grup.codi}</span>
          <span className={styles.mono}>
            {result.grup.cicle_codi ?? ""} · {result.grup.curs}r
          </span>
        </>
      );
    case "cicle":
      return (
        <>
          <span className={styles.kindTag}>cicle</span>
          <span className={styles.label}>
            {result.cicle.codi} · {result.cicle.nom}
          </span>
          <span className={styles.mono}>{result.cicle.nivell}</span>
        </>
      );
    case "shortcut":
      return (
        <>
          <span className={styles.kindTag}>{result.hint ?? "pàgina"}</span>
          <span className={styles.label}>{result.label}</span>
          <span className={styles.mono}>{result.to}</span>
        </>
      );
  }
}
