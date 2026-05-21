/** Avaluacions — list, create, advance state. State flow visualised as a 4-step
 * progress bar matching the mockup. Only admin sees the transition buttons. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { catalogApi, type CursAcademic } from "@/api/catalog";
import type { ApiError } from "@/api/client";
import { gradingApi, type Avaluacio, type EstatAvaluacio } from "@/api/grading";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./AvaluacionsPage.module.css";

const ESTAT_DESC: Record<EstatAvaluacio, string> = {
  oberta: "Configuració inicial: l'admin assigna docents i obre el període.",
  docent: "Els professors introdueixen notes per RA dels seus mòduls.",
  junta: "El tutor revisa i pot modificar qualsevol nota del grup.",
  tancada: "Tot bloquejat. Es generen butlletins PDF i s'envien per email.",
};

const NEXT_STATE: Record<EstatAvaluacio, EstatAvaluacio | null> = {
  oberta: "docent",
  docent: "junta",
  junta: "tancada",
  tancada: null,
};

const PREV_STATE: Record<EstatAvaluacio, EstatAvaluacio | null> = {
  oberta: null,
  docent: "oberta",
  junta: "docent",
  tancada: "junta",
};

const ALL_STATES: EstatAvaluacio[] = ["oberta", "docent", "junta", "tancada"];

export function AvaluacionsPage() {
  const qc = useQueryClient();
  const role = useAuthStore(s => s.user?.role ?? null);
  const isAdmin = role === "admin";

  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });

  const [cursId, setCursId] = useState<number | null>(null);
  useEffect(() => {
    if (cursId !== null) return;
    const actiu = cursos.data?.find((c: CursAcademic) => c.actiu) ?? cursos.data?.[0];
    if (actiu) setCursId(actiu.id);
  }, [cursId, cursos.data]);

  const avals = useQuery({
    queryKey: ["avaluacions", cursId],
    queryFn: () => gradingApi.listAvaluacions(cursId!),
    enabled: cursId !== null,
  });

  const [selected, setSelected] = useState<number | null>(null);
  useEffect(() => {
    if (selected === null && avals.data && avals.data.length > 0) {
      setSelected(avals.data[0]!.id);
    }
  }, [selected, avals.data]);

  const aval = avals.data?.find(a => a.id === selected) ?? null;

  const [createOpen, setCreateOpen] = useState(false);
  const [confirmTransition, setConfirmTransition] = useState<{
    aval: Avaluacio;
    target: EstatAvaluacio;
    direction: "forward" | "rollback";
  } | null>(null);

  const transitionMut = useMutation({
    mutationFn: ({ id, target }: { id: number; target: EstatAvaluacio }) =>
      gradingApi.transition(id, target),
    onSuccess: updated => {
      qc.setQueryData<Avaluacio[]>(["avaluacions", cursId], prev =>
        prev?.map(a => (a.id === updated.id ? updated : a)) ?? prev,
      );
      toast.success(`Estat canviat a "${updated.estat}"`);
    },
    onError: (err: ApiError) => {
      const msg =
        err.code === "permission_denied"
          ? "Només l'admin pot canviar l'estat"
          : err.code === "conflict"
            ? "Transició no permesa des d'aquest estat"
            : err.message || "Error en canviar l'estat";
      toast.error(msg);
    },
  });

  const createMut = useMutation({
    mutationFn: gradingApi.createAvaluacio,
    onSuccess: created => {
      qc.invalidateQueries({ queryKey: ["avaluacions"] });
      setCreateOpen(false);
      setSelected(created.id);
      toast.success(`${created.nom} creada`);
    },
    onError: (err: ApiError) => toast.error(err.message || "No s'ha pogut crear"),
  });

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Curs · Gestió d'avaluacions</p>
        <h1 className={styles.title}>Avaluacions</h1>
        <p className={styles.sub}>
          Cada avaluació passa per quatre estats. L'admin controla la transició; cada
          estat determina qui pot editar quines notes.
        </p>
      </header>

      <div className={styles.toolbar}>
        <CursAcadSelect
          cursos={cursos.data ?? []}
          value={cursId}
          onChange={v => {
            setCursId(v);
            setSelected(null);
          }}
        />
        <span style={{ flex: 1 }} />
        {isAdmin && cursId !== null && (
          <Button variant="primary" onClick={() => setCreateOpen(true)}>
            + Nova avaluació
          </Button>
        )}
      </div>

      <div className={styles.tabs}>
        {avals.data?.map(a => (
          <button
            key={a.id}
            type="button"
            className={`${styles.tab} ${selected === a.id ? styles.tabActive : ""}`}
            onClick={() => setSelected(a.id)}
          >
            <span className={`${styles.dot} ${styles[`dot_${a.estat}`]}`} />
            <span className={styles.tabName}>{a.nom}</span>
            <span className={styles.tabEstat}>{a.estat}</span>
          </button>
        ))}
        {avals.data?.length === 0 && !avals.isLoading && (
          <p className={styles.muted}>Encara no hi ha cap avaluació en aquest curs.</p>
        )}
      </div>

      {aval && (
        <section className={styles.flowCard}>
          <div className={styles.flowHead}>
            <h2>{aval.nom}</h2>
            <p className={styles.flowSub}>
              Inici{" "}
              <span className={styles.mono}>{aval.data_inici ?? "—"}</span>
              {aval.data_tancament && (
                <>
                  {" "}
                  · Tancament{" "}
                  <span className={styles.mono}>{aval.data_tancament}</span>
                </>
              )}
            </p>
          </div>

          <div className={styles.flow}>
            {ALL_STATES.map((st, idx) => {
              const current = aval.estat === st;
              const past = ALL_STATES.indexOf(aval.estat) > idx;
              return (
                <div key={st} className={styles.step} data-state={st}>
                  <div
                    className={`${styles.stepCircle} ${current ? styles.stepCurrent : ""} ${past ? styles.stepPast : ""}`}
                  >
                    {idx + 1}
                  </div>
                  <div className={styles.stepBody}>
                    <div className={styles.stepName}>{st}</div>
                    <div className={styles.stepDesc}>{ESTAT_DESC[st]}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className={styles.flowFoot}>
            <span className={styles.flowEstat}>
              Estat actual: <strong>{aval.estat}</strong>
            </span>
            <span style={{ flex: 1 }} />
            {isAdmin && PREV_STATE[aval.estat] && (
              <Button
                onClick={() =>
                  setConfirmTransition({
                    aval,
                    target: PREV_STATE[aval.estat]!,
                    direction: "rollback",
                  })
                }
              >
                ← Tornar a {PREV_STATE[aval.estat]}
              </Button>
            )}
            {isAdmin && NEXT_STATE[aval.estat] && (
              <Button
                variant="primary"
                onClick={() =>
                  setConfirmTransition({
                    aval,
                    target: NEXT_STATE[aval.estat]!,
                    direction: "forward",
                  })
                }
              >
                Avançar a {NEXT_STATE[aval.estat]} →
              </Button>
            )}
            {!isAdmin && (
              <span className={styles.muted}>Només l'admin pot canviar l'estat</span>
            )}
          </div>
        </section>
      )}

      {confirmTransition && (
        <ConfirmDialog
          title={
            confirmTransition.direction === "forward"
              ? `Avançar a "${confirmTransition.target}"`
              : `Tornar a "${confirmTransition.target}"`
          }
          message={
            confirmTransition.direction === "forward"
              ? `${confirmTransition.aval.nom} passarà de "${confirmTransition.aval.estat}" a "${confirmTransition.target}".`
              : `${confirmTransition.aval.nom} tornarà a "${confirmTransition.target}". Útil per fer correccions abans d'enviar.`
          }
          detail={ESTAT_DESC[confirmTransition.target]}
          confirmLabel={
            confirmTransition.direction === "forward"
              ? `Avançar a ${confirmTransition.target}`
              : `Tornar a ${confirmTransition.target}`
          }
          variant={confirmTransition.direction === "rollback" ? "danger" : "default"}
          onConfirm={() =>
            transitionMut.mutateAsync({
              id: confirmTransition.aval.id,
              target: confirmTransition.target,
            })
          }
          onClose={() => setConfirmTransition(null)}
        />
      )}

      {createOpen && cursId !== null && (
        <CreateAvaluacioModal
          cursAcadId={cursId}
          existingOrdres={avals.data?.map(a => a.ordre) ?? []}
          onClose={() => setCreateOpen(false)}
          onSubmit={body => createMut.mutate(body)}
          submitting={createMut.isPending}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function CursAcadSelect({
  cursos,
  value,
  onChange,
}: {
  cursos: CursAcademic[];
  value: number | null;
  onChange: (v: number) => void;
}) {
  return (
    <label className={styles.cursSelect}>
      <span>Curs acadèmic</span>
      <select value={value ?? ""} onChange={e => onChange(Number(e.target.value))}>
        {cursos.map(c => (
          <option key={c.id} value={c.id}>
            {c.nom} {c.actiu ? "(actiu)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

function CreateAvaluacioModal({
  cursAcadId,
  existingOrdres,
  onClose,
  onSubmit,
  submitting,
}: {
  cursAcadId: number;
  existingOrdres: number[];
  onClose: () => void;
  onSubmit: (body: { curs_acad_id: number; nom: string; ordre: number }) => void;
  submitting: boolean;
}) {
  const nextOrdre = existingOrdres.length === 0 ? 1 : Math.max(...existingOrdres) + 1;
  const [nom, setNom] = useState(`${nextOrdre}a Avaluació`);
  const [ordre, setOrdre] = useState(nextOrdre);

  return (
    <Modal
      title="Nova avaluació"
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <Button onClick={onClose}>Cancel·lar</Button>
          <Button
            variant="primary"
            disabled={submitting || !nom}
            onClick={() => onSubmit({ curs_acad_id: cursAcadId, nom, ordre })}
          >
            {submitting ? "Creant…" : "Crear"}
          </Button>
        </>
      }
    >
      <div className={styles.field}>
        <span>Nom</span>
        <input value={nom} onChange={e => setNom(e.target.value)} />
      </div>
      <div className={styles.field}>
        <span>Ordre</span>
        <input
          type="number"
          min={1}
          max={20}
          value={ordre}
          onChange={e => setOrdre(Number(e.target.value))}
        />
      </div>
    </Modal>
  );
}
