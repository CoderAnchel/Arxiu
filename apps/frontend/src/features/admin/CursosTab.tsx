/** Cursos acadèmics — create + edit + toggle "actiu". */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { catalogApi, type CursAcademic, type CursAcademicCreate } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

export function CursosTab() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const [editing, setEditing] = useState<CursAcademic | "new" | null>(null);
  const [cloning, setCloning] = useState<CursAcademic | null>(null);

  const cloneMut = useMutation({
    mutationFn: ({
      sourceId,
      body,
    }: {
      sourceId: number;
      body: {
        nom: string;
        set_active: boolean;
        clone_grups: boolean;
        clone_assignacions: boolean;
      };
    }) => catalogApi.cloneCurs(sourceId, body),
    onSuccess: c => {
      qc.invalidateQueries({ queryKey: ["cursos"] });
      qc.invalidateQueries({ queryKey: ["grups"] });
      qc.invalidateQueries({ queryKey: ["assignacions"] });
      setCloning(null);
      toast.success(`Curs ${c.nom} creat amb l'estructura clonada`);
    },
    onError: (err: ApiError) => toast.error(err.message || "Error en clonar"),
  });

  const createMut = useMutation({
    mutationFn: (body: CursAcademicCreate) => catalogApi.createCurs(body),
    onSuccess: c => {
      qc.invalidateQueries({ queryKey: ["cursos"] });
      setEditing(null);
      toast.success(`Curs ${c.nom} creat`);
    },
    onError: (err: ApiError) => toast.error(err.message || "No s'ha pogut crear"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<CursAcademicCreate> }) =>
      catalogApi.updateCurs(id, body),
    onSuccess: c => {
      qc.invalidateQueries({ queryKey: ["cursos"] });
      setEditing(null);
      toast.success(`Curs ${c.nom} actualitzat`);
    },
    onError: () => toast.error("Error en actualitzar"),
  });

  const toggleActiu = (c: CursAcademic) =>
    updateMut.mutate({ id: c.id, body: { actiu: !c.actiu } });

  return (
    <>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>
          {list.data?.length ?? 0} cursos acadèmics
        </span>
        <div className={styles.toolbar}>
          <Button variant="primary" onClick={() => setEditing("new")}>
            + Nou curs acadèmic
          </Button>
        </div>
      </div>

      {list.isLoading && <p className={styles.muted}>Carregant…</p>}
      {list.data && list.data.length === 0 && (
        <p className={styles.muted}>
          Encara no hi ha cap curs creat. Crea el primer (per exemple "2025-2026").
        </p>
      )}
      {list.data && list.data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Curs</th>
              <th>Inici</th>
              <th>Fi</th>
              <th>Actiu</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.data.map(c => (
              <tr key={c.id}>
                <td>
                  <strong>{c.nom}</strong>
                </td>
                <td className={styles.mono}>{c.data_inici ?? "—"}</td>
                <td className={styles.mono}>{c.data_fi ?? "—"}</td>
                <td>
                  {c.actiu ? (
                    <span className={styles.actiuTag}>actiu</span>
                  ) : (
                    <span className={styles.mono}>—</span>
                  )}
                </td>
                <td>
                  <div className={styles.rowActions}>
                    <Button size="sm" onClick={() => setEditing(c)}>
                      Editar
                    </Button>
                    <Button size="sm" onClick={() => toggleActiu(c)}>
                      {c.actiu ? "Desactivar" : "Activar"}
                    </Button>
                    <Button size="sm" onClick={() => setCloning(c)}>
                      Clonar →
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <CursModal
          curs={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSubmit={body => {
            if (editing === "new") createMut.mutate(body);
            else updateMut.mutate({ id: editing.id, body });
          }}
          submitting={createMut.isPending || updateMut.isPending}
        />
      )}

      {cloning && (
        <CloneCursModal
          source={cloning}
          onClose={() => setCloning(null)}
          onSubmit={body =>
            cloneMut.mutate({ sourceId: cloning.id, body })
          }
          submitting={cloneMut.isPending}
        />
      )}
    </>
  );
}

function CloneCursModal({
  source,
  onClose,
  onSubmit,
  submitting,
}: {
  source: CursAcademic;
  onClose: () => void;
  onSubmit: (body: {
    nom: string;
    set_active: boolean;
    clone_grups: boolean;
    clone_assignacions: boolean;
  }) => void;
  submitting: boolean;
}) {
  // Suggest "next year": parse "2025-2026" → "2026-2027"
  const suggestNextNom = (current: string): string => {
    const m = /^(\d{4})-(\d{4})$/.exec(current);
    if (!m) return current + " (còpia)";
    const a = Number(m[1]);
    const b = Number(m[2]);
    return `${a + 1}-${b + 1}`;
  };

  const [nom, setNom] = useState(suggestNextNom(source.nom));
  const [setActive, setSetActive] = useState(true);
  const [cloneGrups, setCloneGrups] = useState(true);
  const [cloneAssignacions, setCloneAssignacions] = useState(true);

  return (
    <Modal
      title={`Clonar estructura de ${source.nom}`}
      onClose={onClose}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || !nom.trim()}
            onClick={() =>
              onSubmit({
                nom: nom.trim(),
                set_active: setActive,
                clone_grups: cloneGrups,
                clone_assignacions: cloneAssignacions,
              })
            }
          >
            {submitting ? "Clonant…" : `Crear ${nom.trim()}`}
          </Button>
        </>
      }
    >
      <p className={styles.muted} style={{ margin: "0 0 14px", padding: 0 }}>
        Crearàs un curs acadèmic nou amb la mateixa estructura de grups (i
        opcionalment assignacions docents) que <strong>{source.nom}</strong>.
        Les matrícules i les notes <strong>no es clonen</strong> — cada curs té
        els seus alumnes i avaluacions.
      </p>
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Nom del nou curs *</span>
          <input
            value={nom}
            onChange={e => setNom(e.target.value)}
            placeholder="2026-2027"
            autoFocus
          />
        </label>
        <label className={`${styles.checkbox} ${styles.full}`}>
          <input
            type="checkbox"
            checked={setActive}
            onChange={e => setSetActive(e.target.checked)}
          />
          <span>Marcar el curs nou com a actiu (desactiva el curs actual)</span>
        </label>
        <label className={`${styles.checkbox} ${styles.full}`}>
          <input
            type="checkbox"
            checked={cloneGrups}
            onChange={e => setCloneGrups(e.target.checked)}
          />
          <span>Clonar els grups (codis, cicle, curs, tutor)</span>
        </label>
        <label className={`${styles.checkbox} ${styles.full}`}>
          <input
            type="checkbox"
            checked={cloneAssignacions}
            onChange={e => setCloneAssignacions(e.target.checked)}
            disabled={!cloneGrups}
          />
          <span>
            Clonar també les assignacions docents{" "}
            <em style={{ color: "var(--ink-3)" }}>(necessita clonar grups)</em>
          </span>
        </label>
      </div>
    </Modal>
  );
}

function CursModal({
  curs,
  onClose,
  onSubmit,
  submitting,
}: {
  curs: CursAcademic | null;
  onClose: () => void;
  onSubmit: (body: CursAcademicCreate) => void;
  submitting: boolean;
}) {
  const [nom, setNom] = useState(curs?.nom ?? "");
  const [actiu, setActiu] = useState(curs?.actiu ?? false);
  const [dataInici, setDataInici] = useState(curs?.data_inici ?? "");
  const [dataFi, setDataFi] = useState(curs?.data_fi ?? "");

  const handle = () => {
    if (!nom.trim()) return;
    onSubmit({
      nom: nom.trim(),
      actiu,
      data_inici: dataInici || null,
      data_fi: dataFi || null,
    });
  };

  return (
    <Modal
      title={curs ? "Editar curs acadèmic" : "Nou curs acadèmic"}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button variant="primary" disabled={submitting || !nom.trim()} onClick={handle}>
            {submitting ? "Desant…" : curs ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Nom *</span>
          <input
            value={nom}
            onChange={e => setNom(e.target.value)}
            placeholder="2025-2026"
            autoFocus
          />
        </label>
        <label className={styles.field}>
          <span>Data inici</span>
          <input
            type="date"
            value={dataInici}
            onChange={e => setDataInici(e.target.value)}
          />
        </label>
        <label className={styles.field}>
          <span>Data fi</span>
          <input
            type="date"
            value={dataFi}
            onChange={e => setDataFi(e.target.value)}
          />
        </label>
        <label className={`${styles.checkbox} ${styles.full}`}>
          <input
            type="checkbox"
            checked={actiu}
            onChange={e => setActiu(e.target.checked)}
          />
          <span>Marcar com a curs actiu (desactivarà els altres automàticament)</span>
        </label>
      </div>
    </Modal>
  );
}
