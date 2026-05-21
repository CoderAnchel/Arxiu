/** Paperera — list + restore soft-deleted items.
 *
 * Admin-only. Tab per entity kind, with a "Restore" button on each row.
 * The data is never actually erased; restore just clears deleted_at.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { trashApi, type TrashKind } from "@/api/trash";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { toast } from "@/stores/toastStore";

import styles from "./TrashPage.module.css";

const KIND_LABELS: Record<TrashKind, string> = {
  alumne: "Alumnes",
  cicle: "Cicles",
  modul: "Mòduls",
  ra: "Resultats d'aprenentatge",
  grup: "Grups",
  matricula: "Matrícules",
  assignacio_docent: "Assignacions docents",
};

const KIND_ORDER: TrashKind[] = [
  "alumne",
  "grup",
  "matricula",
  "assignacio_docent",
  "cicle",
  "modul",
  "ra",
];

export function TrashPage() {
  const qc = useQueryClient();
  const trash = useQuery({ queryKey: ["trash"], queryFn: () => trashApi.list() });
  const [confirmRestore, setConfirmRestore] = useState<{
    kind: TrashKind;
    id: number;
    label: string;
  } | null>(null);

  const restoreMut = useMutation({
    mutationFn: ({ kind, id }: { kind: TrashKind; id: number }) =>
      trashApi.restore(kind, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trash"] });
      qc.invalidateQueries(); // anything could have changed
      setConfirmRestore(null);
      toast.success("Element restaurat");
    },
    onError: () => toast.error("No s'ha pogut restaurar"),
  });

  const total = trash.data
    ? Object.values(trash.data).reduce((acc, list) => acc + list.length, 0)
    : 0;

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Paperera · Arxiu permanent</p>
        <h1 className={styles.title}>Elements eliminats</h1>
        <p className={styles.sub}>
          Tot el que s'ha donat de baixa de l'arxiu actiu queda aquí. Res s'ha
          esborrat de la base de dades — pots restaurar qualsevol element i
          tornarà a aparèixer als llistats. Les notes històriques associades a
          un alumne/mòdul/RA es preserven sempre.
        </p>
        <p className={styles.count}>
          {trash.isLoading ? "Carregant…" : `${total} elements eliminats`}
        </p>
      </header>

      {trash.data &&
        KIND_ORDER.map(kind => {
          const items = trash.data[kind] ?? [];
          if (items.length === 0) return null;
          return (
            <section key={kind} className={styles.card}>
              <div className={styles.cardHead}>
                <h2>{KIND_LABELS[kind]}</h2>
                <span className={styles.muted}>
                  {items.length} {items.length === 1 ? "element" : "elements"}
                </span>
              </div>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Identificador</th>
                    <th>Detall</th>
                    <th>Eliminat el</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {items.map(it => (
                    <tr key={it.id}>
                      <td>
                        <strong>{it.label}</strong>
                      </td>
                      <td className={styles.sub}>{it.sub}</td>
                      <td className={styles.mono}>
                        {it.deleted_at
                          ? new Date(it.deleted_at).toLocaleString("ca-ES")
                          : "—"}
                      </td>
                      <td>
                        <Button
                          size="sm"
                          onClick={() =>
                            setConfirmRestore({ kind, id: it.id, label: it.label })
                          }
                        >
                          Restaurar
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          );
        })}

      {trash.data && total === 0 && (
        <p className={styles.empty}>
          No hi ha cap element a la paperera. Tot l'arxiu actiu està net.
        </p>
      )}

      {confirmRestore && (
        <ConfirmDialog
          title="Restaurar element"
          message={`Es restaurarà "${confirmRestore.label}" i tornarà a aparèixer als llistats actius.`}
          confirmLabel={restoreMut.isPending ? "Restaurant…" : "Restaurar"}
          onConfirm={() =>
            restoreMut.mutate({ kind: confirmRestore.kind, id: confirmRestore.id })
          }
          onClose={() => !restoreMut.isPending && setConfirmRestore(null)}
        />
      )}
    </div>
  );
}
