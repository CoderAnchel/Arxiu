/** Famílies professionals — list + create + edit + soft-delete.
 *
 * Each cicle pertany a una família (Informàtica, Sanitat, Administració…).
 * Mantenir-les netes evita haver de tocar la DB i facilita el filtre de
 * cicles a /curriculums.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { catalogApi, type Familia } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

export function FamiliesTab() {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["families"], queryFn: () => catalogApi.listFamilies() });
  const [editing, setEditing] = useState<Familia | "new" | null>(null);
  const [deleting, setDeleting] = useState<Familia | null>(null);

  const createMut = useMutation({
    mutationFn: (body: { codi: string; nom: string }) => catalogApi.createFamilia(body),
    onSuccess: f => {
      qc.invalidateQueries({ queryKey: ["families"] });
      setEditing(null);
      toast.success(`Família ${f.codi} creada`);
    },
    onError: (err: ApiError) =>
      toast.error(
        err.code === "conflict"
          ? "Ja existeix una família amb aquest codi"
          : err.message || "Error en crear",
      ),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<{ codi: string; nom: string }> }) =>
      catalogApi.updateFamilia(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["families"] });
      setEditing(null);
      toast.success("Família actualitzada");
    },
    onError: (err: ApiError) => toast.error(err.message || "Error en actualitzar"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => catalogApi.deleteFamilia(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["families"] });
      setDeleting(null);
      toast.success("Família eliminada");
    },
    onError: () => toast.error("Error en eliminar"),
  });

  return (
    <>
      <div className={styles.panelHead}>
        <span className={styles.panelTitle}>
          {list.data?.length ?? 0} famílies professionals
        </span>
        <div className={styles.toolbar}>
          <Button variant="primary" onClick={() => setEditing("new")}>
            + Nova família
          </Button>
        </div>
      </div>

      {list.isLoading && <p className={styles.muted}>Carregant…</p>}
      {list.data && list.data.length === 0 && (
        <p className={styles.muted}>
          Encara no hi ha cap família. Crea'n una (per exemple "Informàtica i comunicacions").
        </p>
      )}
      {list.data && list.data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Codi</th>
              <th>Nom</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.data.map(f => (
              <tr key={f.id}>
                <td>
                  <strong className={styles.mono}>{f.codi}</strong>
                </td>
                <td>{f.nom}</td>
                <td>
                  <div className={styles.rowActions}>
                    <Button size="sm" onClick={() => setEditing(f)}>
                      Editar
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => setDeleting(f)}>
                      Eliminar
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <FamiliaModal
          familia={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSubmit={body => {
            if (editing === "new") createMut.mutate(body);
            else updateMut.mutate({ id: editing.id, body });
          }}
          submitting={createMut.isPending || updateMut.isPending}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title={`Eliminar família ${deleting.codi}?`}
          message="Si hi ha cicles que pertanyen a aquesta família, quedaran sense família associada (es podrà reassignar a posteriori). Soft delete: pots restaurar-la des de la paperera."
          variant="danger"
          confirmLabel="Eliminar"
          onConfirm={() => deleteMut.mutate(deleting.id)}
          onClose={() => setDeleting(null)}
        />
      )}
    </>
  );
}

/** Exported so it can be reused inline from other forms (ex: CicleFormModal). */
export function FamiliaModal({
  familia,
  onClose,
  onSubmit,
  submitting,
}: {
  familia: Familia | null;
  onClose: () => void;
  onSubmit: (body: { codi: string; nom: string }) => void;
  submitting: boolean;
}) {
  const [codi, setCodi] = useState(familia?.codi ?? "");
  const [nom, setNom] = useState(familia?.nom ?? "");
  const valid = codi.trim().length > 0 && nom.trim().length > 0;

  return (
    <Modal
      title={familia ? "Editar família" : "Nova família professional"}
      onClose={onClose}
      maxWidth={480}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={!valid || submitting}
            onClick={() => onSubmit({ codi: codi.trim().toUpperCase(), nom: nom.trim() })}
          >
            {submitting ? "Desant…" : familia ? "Guardar" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.fieldMono}`}>
          <span>Codi *</span>
          <input
            value={codi}
            onChange={e => setCodi(e.target.value.toUpperCase())}
            placeholder="IFC"
            autoFocus
          />
        </label>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Nom *</span>
          <input
            value={nom}
            onChange={e => setNom(e.target.value)}
            placeholder="Informàtica i comunicacions"
          />
        </label>
      </div>
    </Modal>
  );
}
