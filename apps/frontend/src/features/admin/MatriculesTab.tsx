/** Matrícules — list + create. Permits filtering by grup. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { catalogApi } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import {
  grupsApi,
  matriculesApi,
  type Matricula,
  type MatriculaCreate,
} from "@/api/grups";
import { peopleApi, type Alumne } from "@/api/people";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/stores/toastStore";

import styles from "./AdminPage.module.css";

export function MatriculesTab() {
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

  const matr = useQuery({
    queryKey: ["matricules", grupId, cursId],
    queryFn: () => matriculesApi.list({ grup_id: grupId!, curs_acad_id: cursId ?? undefined }),
    enabled: grupId !== null,
  });
  const alumnes = useQuery({
    queryKey: ["alumnes-all"],
    queryFn: () => peopleApi.listAlumnes({ limit: 500 }),
  });

  const alumneById = useMemo(() => {
    const m = new Map<number, Alumne>();
    for (const a of alumnes.data ?? []) m.set(a.id, a);
    return m;
  }, [alumnes.data]);

  const [creating, setCreating] = useState(false);

  const createMut = useMutation({
    mutationFn: (body: MatriculaCreate) => matriculesApi.create(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["matricules"] });
      setCreating(false);
      toast.success("Matrícula creada");
    },
    onError: (err: ApiError) =>
      toast.error(
        err.code === "conflict"
          ? "Aquest alumne ja està matriculat al cicle d'aquest curs"
          : err.message || "Error en crear",
      ),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<MatriculaCreate, "estat">> }) =>
      matriculesApi.update(id, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["matricules"] }),
  });

  const grup = grups.data?.find(g => g.id === grupId);

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
          <span className={styles.panelTitle}>{matr.data?.length ?? 0} matrícules</span>
        </div>
        <Button
          variant="primary"
          onClick={() => setCreating(true)}
          disabled={grupId === null}
        >
          + Inscriure alumne
        </Button>
      </div>

      {matr.isLoading && <p className={styles.muted}>Carregant…</p>}
      {matr.data && matr.data.length === 0 && (
        <p className={styles.muted}>Cap alumne matriculat a aquest grup.</p>
      )}
      {matr.data && matr.data.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Alumne</th>
              <th>DNI</th>
              <th>Tipus</th>
              <th>Estat</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {matr.data.map(m => {
              const a = alumneById.get(m.alumne_id);
              return (
                <tr key={m.id}>
                  <td>
                    {a ? (
                      <>
                        <strong>{a.cognoms}, {a.nom}</strong>
                        <div className={styles.mono}>RALC {a.ralc}</div>
                      </>
                    ) : (
                      <span className={styles.mono}>#{m.alumne_id}</span>
                    )}
                  </td>
                  <td className={styles.mono}>{a?.dni ?? "—"}</td>
                  <td className={styles.mono}>{m.tipus}</td>
                  <td>
                    <span className={`${styles.estatTag} ${styles[`estat_${m.estat}`]}`}>
                      {m.estat}
                    </span>
                  </td>
                  <td>
                    <div className={styles.rowActions}>
                      <select
                        value={m.estat}
                        onChange={e =>
                          updateMut.mutate({
                            id: m.id,
                            body: { estat: e.target.value as Matricula["estat"] },
                          })
                        }
                        className={styles.mono}
                      >
                        <option value="actiu">actiu</option>
                        <option value="finalitzat">finalitzat</option>
                        <option value="baixa">baixa</option>
                      </select>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {creating && grup && cursId !== null && (
        <NewMatriculaModal
          grup={grup}
          cursAcadId={cursId}
          alumnes={alumnes.data ?? []}
          existingAlumneIds={new Set((matr.data ?? []).map(m => m.alumne_id))}
          onClose={() => setCreating(false)}
          onSubmit={body => createMut.mutate(body)}
          submitting={createMut.isPending}
        />
      )}
    </>
  );
}

function NewMatriculaModal({
  grup,
  cursAcadId,
  alumnes,
  existingAlumneIds,
  onClose,
  onSubmit,
  submitting,
}: {
  grup: { id: number; cicle_id: number; curs: number; codi: string };
  cursAcadId: number;
  alumnes: Alumne[];
  existingAlumneIds: Set<number>;
  onClose: () => void;
  onSubmit: (body: MatriculaCreate) => void;
  submitting: boolean;
}) {
  const [alumneId, setAlumneId] = useState<number | null>(null);
  const [tipus, setTipus] = useState<MatriculaCreate["tipus"]>("primari");
  const eligible = alumnes.filter(a => !existingAlumneIds.has(a.id));

  return (
    <Modal
      title={`Inscriure alumne · ${grup.codi}`}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || alumneId === null}
            onClick={() =>
              onSubmit({
                alumne_id: alumneId!,
                grup_id: grup.id,
                cicle_id: grup.cicle_id,
                curs: grup.curs,
                curs_acad_id: cursAcadId,
                tipus,
                estat: "actiu",
              })
            }
          >
            {submitting ? "Inscrivint…" : "Inscriure"}
          </Button>
        </>
      }
    >
      <div className={styles.formGrid}>
        <label className={`${styles.field} ${styles.full}`}>
          <span>Alumne *</span>
          <select
            value={alumneId ?? ""}
            onChange={e => setAlumneId(Number(e.target.value) || null)}
            autoFocus
          >
            <option value="">— selecciona —</option>
            {eligible.map(a => (
              <option key={a.id} value={a.id}>
                {a.cognoms}, {a.nom} · RALC {a.ralc}
              </option>
            ))}
          </select>
          {eligible.length === 0 && (
            <small style={{ color: "var(--ink-3)" }}>
              Tots els alumnes ja estan matriculats en aquest grup. Crea'n un de nou
              a la pàgina d'Alumnes.
            </small>
          )}
        </label>
        <label className={styles.field}>
          <span>Tipus</span>
          <select
            value={tipus}
            onChange={e => setTipus(e.target.value as MatriculaCreate["tipus"])}
          >
            <option value="primari">Primari</option>
            <option value="secundari">Secundari</option>
          </select>
        </label>
      </div>
    </Modal>
  );
}
