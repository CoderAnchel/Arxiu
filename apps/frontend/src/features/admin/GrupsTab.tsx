/** Grups classe — list + create + edit (codi, cicle, curs, tutor). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { adminApi } from "@/api/admin";
import { catalogApi } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { grupsApi, type Grup, type GrupCreate } from "@/api/grups";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

export function GrupsTab() {
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

  const [editing, setEditing] = useState<Grup | "new" | null>(null);

  const createMut = useMutation({
    mutationFn: (body: GrupCreate) => grupsApi.create(body),
    onSuccess: g => {
      qc.invalidateQueries({ queryKey: ["grups"] });
      setEditing(null);
      toast.success(`Grup ${g.codi} creat`);
    },
    onError: (err: ApiError) =>
      toast.error(
        err.code === "conflict"
          ? "Ja existeix un grup amb aquest codi al curs"
          : err.message || "Error en crear",
      ),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<GrupCreate> }) =>
      grupsApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grups"] });
      setEditing(null);
      toast.success("Grup actualitzat");
    },
    onError: () => toast.error("Error en actualitzar"),
  });

  return (
    <>
      <div className={styles.panelHead}>
        <div className={styles.toolbar}>
          <label className={styles.toolbarSelect}>
            <span>Curs acadèmic</span>
            <select
              value={cursId ?? ""}
              onChange={e => setCursId(Number(e.target.value))}
            >
              {(cursos.data ?? []).map(c => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                  {c.actiu ? " · actiu" : ""}
                </option>
              ))}
            </select>
          </label>
          <span className={styles.panelTitle}>{grups.data?.length ?? 0} grups</span>
        </div>
        <Button variant="primary" onClick={() => setEditing("new")} disabled={cursId === null}>
          + Nou grup
        </Button>
      </div>

      {grups.isLoading && <p className={styles.muted}>Carregant…</p>}
      {grups.data && grups.data.length === 0 && (
        <p className={styles.muted}>Cap grup en aquest curs.</p>
      )}
      {grups.data && grups.data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Codi</th>
              <th>Cicle</th>
              <th>Curs (1r/2n)</th>
              <th>Tutor</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {grups.data.map(g => (
              <tr key={g.id}>
                <td>
                  <strong>{g.codi}</strong>
                </td>
                <td className={styles.mono}>{g.cicle_codi ?? `cicle #${g.cicle_id}`}</td>
                <td className={styles.mono}>{g.curs}r</td>
                <td>{g.tutor_nom_complet ?? <span className={styles.mono}>sense tutor</span>}</td>
                <td>
                  <div className={styles.rowActions}>
                    <Button size="sm" onClick={() => setEditing(g)}>
                      Editar
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && cursId !== null && (
        <GrupModal
          grup={editing === "new" ? null : editing}
          defaultCursId={cursId}
          onClose={() => setEditing(null)}
          onSubmit={body => {
            if (editing === "new") createMut.mutate(body);
            else updateMut.mutate({ id: editing.id, body });
          }}
          submitting={createMut.isPending || updateMut.isPending}
        />
      )}
    </>
  );
}

function GrupModal({
  grup,
  defaultCursId,
  onClose,
  onSubmit,
  submitting,
}: {
  grup: Grup | null;
  defaultCursId: number;
  onClose: () => void;
  onSubmit: (body: GrupCreate) => void;
  submitting: boolean;
}) {
  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const cicles = useQuery({ queryKey: ["cicles"], queryFn: () => catalogApi.listCicles() });
  const docents = useQuery({ queryKey: ["admin-users"], queryFn: () => adminApi.list() });
  const professors = (docents.data ?? []).filter(d => d.active);

  const [form, setForm] = useState<GrupCreate>({
    codi: grup?.codi ?? "",
    curs_acad_id: grup?.curs_acad_id ?? defaultCursId,
    cicle_id: grup?.cicle_id ?? 0,
    curs: grup?.curs ?? 1,
    tutor_user_id: grup?.tutor_user_id ?? null,
  });
  const set = <K extends keyof GrupCreate>(k: K, v: GrupCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }));

  useEffect(() => {
    if (form.cicle_id === 0 && cicles.data && cicles.data.length > 0) {
      set("cicle_id", cicles.data[0]!.id);
    }
  }, [cicles.data]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal
      title={grup ? "Editar grup" : "Nou grup classe"}
      onClose={onClose}
      maxWidth={560}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || !form.codi.trim() || form.cicle_id === 0}
            onClick={() => onSubmit({ ...form, codi: form.codi.trim() })}
          >
            {submitting ? "Desant…" : grup ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.fieldMono}`}>
          <span>Codi *</span>
          <input
            value={form.codi}
            onChange={e => set("codi", e.target.value.toUpperCase())}
            placeholder="DAM1A"
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Curs acadèmic *</span>
          <select
            value={form.curs_acad_id}
            onChange={e => set("curs_acad_id", Number(e.target.value))}
          >
            {(cursos.data ?? []).map(c => (
              <option key={c.id} value={c.id}>
                {c.nom}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span>Cicle *</span>
          <select
            value={form.cicle_id}
            onChange={e => set("cicle_id", Number(e.target.value))}
          >
            {(cicles.data ?? []).map(c => (
              <option key={c.id} value={c.id}>
                {c.codi} · {c.nom}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          <span>Curs (1r o 2n)</span>
          <select value={form.curs} onChange={e => set("curs", Number(e.target.value))}>
            <option value={1}>1r curs</option>
            <option value={2}>2n curs</option>
          </select>
        </label>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Tutor/a</span>
          <select
            value={form.tutor_user_id ?? ""}
            onChange={e =>
              set("tutor_user_id", e.target.value ? Number(e.target.value) : null)
            }
          >
            <option value="">— sense tutor —</option>
            {professors.map(d => (
              <option key={d.id} value={d.id}>
                {d.nom} {d.cognoms} ({d.role})
              </option>
            ))}
          </select>
        </label>
      </div>
    </Modal>
  );
}
