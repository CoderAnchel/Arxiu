/** Assignacions docents — quins profes donen quins mòduls a quin grup.
 * Un mòdul d'un grup pot tenir DIVERSOS profes (co-titularitats). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { adminApi } from "@/api/admin";
import { catalogApi, type Modul } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import {
  assignacionsApi,
  grupsApi,
  type AssignacioDocentCreate,
} from "@/api/grups";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

export function AssignacionsTab() {
  const qc = useQueryClient();
  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const [cursId, setCursId] = useState<number | null>(null);
  useEffect(() => {
    if (cursId !== null) return;
    const a = cursos.data?.find(c => c.actiu) ?? cursos.data?.[0];
    if (a) setCursId(a.id);
  }, [cursId, cursos.data]);

  const grups = useQuery({
    queryKey: ["grups", cursId],
    queryFn: () => grupsApi.list(cursId ?? undefined),
    enabled: cursId !== null,
  });
  const [grupId, setGrupId] = useState<number | null>(null);
  useEffect(() => {
    if (grupId === null && grups.data && grups.data.length > 0) setGrupId(grups.data[0]!.id);
    if (grupId !== null && grups.data && !grups.data.some(g => g.id === grupId)) {
      setGrupId(grups.data[0]?.id ?? null);
    }
  }, [grupId, grups.data]);

  const grup = grups.data?.find(g => g.id === grupId) ?? null;
  const moduls = useQuery({
    queryKey: ["moduls", grup?.cicle_id],
    queryFn: () => catalogApi.listModuls(grup!.cicle_id),
    enabled: grup !== null,
  });

  const assigs = useQuery({
    queryKey: ["assignacions", grupId, cursId],
    queryFn: () =>
      assignacionsApi.list({ grup_id: grupId!, curs_acad_id: cursId ?? undefined }),
    enabled: grupId !== null,
  });

  const docents = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.list() });
  const docentById = useMemo(() => {
    const m = new Map<number, (typeof docents.data extends (infer T)[] ? T : never)>();
    for (const d of docents.data ?? []) m.set(d.id, d);
    return m;
  }, [docents.data]);
  const modulById = useMemo(() => {
    const m = new Map<number, Modul>();
    for (const x of moduls.data ?? []) m.set(x.id, x);
    return m;
  }, [moduls.data]);

  const [creating, setCreating] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const createMut = useMutation({
    mutationFn: (body: AssignacioDocentCreate) => assignacionsApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignacions"] });
      setCreating(false);
      toast.success("Assignació creada");
    },
    onError: (err: ApiError) =>
      toast.error(
        err.code === "conflict"
          ? "Aquesta combinació professor + grup + mòdul ja existeix"
          : err.message || "Error en crear",
      ),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => assignacionsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["assignacions"] });
      setConfirmDelete(null);
      toast.success("Assignació eliminada");
    },
    onError: () => toast.error("Error en eliminar"),
  });

  // Group assignations by mòdul → list of profes
  const grouped = useMemo(() => {
    const m = new Map<number, typeof assigs.data extends (infer T)[] ? T[] : never[]>();
    for (const a of assigs.data ?? []) {
      const arr = m.get(a.modul_id) ?? [];
      arr.push(a);
      m.set(a.modul_id, arr);
    }
    return m;
  }, [assigs.data]);

  return (
    <>
      <div className={styles.panelHead}>
        <div className={styles.toolbar}>
          <label className={styles.toolbarSelect}>
            <span>Curs</span>
            <select
              value={cursId ?? ""}
              onChange={e => {
                setCursId(Number(e.target.value));
                setGrupId(null);
              }}
            >
              {(cursos.data ?? []).map(c => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.toolbarSelect}>
            <span>Grup</span>
            <select value={grupId ?? ""} onChange={e => setGrupId(Number(e.target.value))}>
              {(grups.data ?? []).map(g => (
                <option key={g.id} value={g.id}>
                  {g.codi} · {g.cicle_codi}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Button
          variant="primary"
          onClick={() => setCreating(true)}
          disabled={grupId === null}
        >
          + Assignar professor
        </Button>
      </div>

      {assigs.isLoading && <p className={styles.muted}>Carregant…</p>}
      {moduls.data && moduls.data.length === 0 && (
        <p className={styles.muted}>El cicle d'aquest grup no té cap mòdul.</p>
      )}
      {moduls.data && moduls.data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Mòdul</th>
              <th>Curs</th>
              <th>Professors assignats</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {moduls.data
              .filter(m => grup && m.curs === grup.curs)
              .map(m => {
                const rows = grouped.get(m.id) ?? [];
                return (
                  <tr key={m.id}>
                    <td>
                      <strong>{m.codi}</strong>
                      <div className={styles.mono}>{m.nom}</div>
                    </td>
                    <td className={styles.mono}>{m.curs}r</td>
                    <td>
                      {rows.length === 0 && (
                        <span className={styles.mono}>cap assignació</span>
                      )}
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                        {rows.map(a => {
                          const d = docentById.get(a.user_id);
                          return (
                            <span
                              key={a.id}
                              className={styles.estatTag}
                              style={{
                                background: "var(--bg-2)",
                                color: "var(--ink)",
                                cursor: "pointer",
                              }}
                              onClick={() => setConfirmDelete(a.id)}
                              title="Click per eliminar"
                            >
                              {d ? `${d.nom} ${d.cognoms}` : `#${a.user_id}`} ×
                            </span>
                          );
                        })}
                      </div>
                    </td>
                    <td />
                  </tr>
                );
              })}
          </tbody>
        </table>
      )}

      {creating && grup && cursId !== null && (
        <NewAssignacioModal
          grup={grup}
          cursAcadId={cursId}
          moduls={(moduls.data ?? []).filter(m => m.curs === grup.curs)}
          docents={(docents.data ?? []).filter(d => d.active)}
          onClose={() => setCreating(false)}
          onSubmit={body => createMut.mutate(body)}
          submitting={createMut.isPending}
        />
      )}

      {confirmDelete && (
        <ConfirmDialog
          title="Eliminar assignació"
          message="Aquest professor deixarà de tenir accés a aquest mòdul d'aquest grup."
          variant="danger"
          confirmLabel="Eliminar"
          onConfirm={() => deleteMut.mutate(confirmDelete)}
          onClose={() => setConfirmDelete(null)}
        />
      )}
    </>
  );
}

function NewAssignacioModal({
  grup,
  cursAcadId,
  moduls,
  docents,
  onClose,
  onSubmit,
  submitting,
}: {
  grup: { id: number; codi: string };
  cursAcadId: number;
  moduls: Modul[];
  docents: { id: number; nom: string; cognoms: string; role: string }[];
  onClose: () => void;
  onSubmit: (body: AssignacioDocentCreate) => void;
  submitting: boolean;
}) {
  const [modulId, setModulId] = useState<number | null>(moduls[0]?.id ?? null);
  const [userIds, setUserIds] = useState<number[]>([]);

  const handle = () => {
    if (modulId === null) return;
    // Send one POST per professor
    for (const uid of userIds) {
      onSubmit({
        user_id: uid,
        grup_id: grup.id,
        modul_id: modulId,
        curs_acad_id: cursAcadId,
      });
    }
  };

  return (
    <Modal
      title={`Assignar professor/s · ${grup.codi}`}
      onClose={onClose}
      maxWidth={500}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || modulId === null || userIds.length === 0}
            onClick={handle}
          >
            {submitting
              ? "Creant…"
              : `Crear ${userIds.length || ""} assignacions`}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Mòdul *</span>
          <select
            value={modulId ?? ""}
            onChange={e => setModulId(Number(e.target.value))}
          >
            {moduls.map(m => (
              <option key={m.id} value={m.id}>
                {m.codi} · {m.nom}
              </option>
            ))}
          </select>
        </label>
        <div className={`${styles.field} ${styles.full}`}>
          <span>Professors *</span>
          <div
            style={{
              background: "var(--bg-2)",
              border: "1px solid var(--line)",
              borderRadius: "var(--r)",
              maxHeight: 220,
              overflowY: "auto",
              padding: 6,
            }}
          >
            {docents.map(d => {
              const checked = userIds.includes(d.id);
              return (
                <label
                  key={d.id}
                  className={styles.checkbox}
                  style={{ padding: "6px 10px", cursor: "pointer" }}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      setUserIds(prev =>
                        checked ? prev.filter(x => x !== d.id) : [...prev, d.id],
                      )
                    }
                  />
                  <span>
                    {d.nom} {d.cognoms}{" "}
                    <span style={{ color: "var(--ink-3)", fontFamily: "var(--mono)", fontSize: 11 }}>
                      ({d.role})
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
          <small style={{ color: "var(--ink-3)" }}>
            Pots assignar diversos professors al mateix mòdul (co-titularitat).
          </small>
        </div>
      </div>
    </Modal>
  );
}
