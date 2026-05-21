/** Alumnes — list + search + create/edit modal + soft-delete. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { peopleApi, type Alumne } from "@/api/people";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import { AlumneFormModal } from "./AlumneFormModal";
import styles from "./AlumnesPage.module.css";

export function AlumnesPage() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isAdmin = useAuthStore(s => s.user?.role === "admin");
  const [q, setQ] = useState("");
  const deferredQ = useDeferredValue(q);
  const [selected, setSelected] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<Alumne | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);

  // Honour ?selected=ID from cross-page links (e.g. coming back from expedient).
  useEffect(() => {
    const target = searchParams.get("selected");
    if (target) setSelected(Number(target));
  }, [searchParams]);

  const list = useQuery({
    queryKey: ["alumnes", deferredQ],
    queryFn: () => peopleApi.listAlumnes({ q: deferredQ || undefined, limit: 100 }),
    placeholderData: prev => prev,
  });

  const detail = useQuery({
    queryKey: ["alumne", selected],
    queryFn: () => peopleApi.getAlumne(selected!),
    enabled: selected !== null,
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => peopleApi.deleteAlumne(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["alumnes"] });
      setSelected(null);
      toast.success("Alumne donat de baixa de l'arxiu actiu");
    },
    onError: () => toast.error("No s'ha pogut donar de baixa"),
  });

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>{list.data?.length ?? 0} alumnes a la cerca</p>
        <h1 className={styles.title}>Alumnes</h1>
        <p className={styles.sub}>
          Cerca per nom, DNI, RALC o email. La fitxa completa amb matrícules viu a
          l'Arxiu (Phase 3).
        </p>
      </header>

      <div className={styles.toolbar}>
        <input
          type="search"
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="Cerca: nom, cognoms, DNI, RALC, email…"
          className={styles.search}
        />
        {isAdmin && (
          <>
            <Button variant="primary" onClick={() => setFormMode("create")}>
              + Nou alumne
            </Button>
            <Button onClick={() => navigate("/importacions")}>Importar Excel</Button>
          </>
        )}
      </div>

      <div className={styles.layout}>
        <section className={styles.tableWrap}>
          {list.isLoading && <div className={styles.muted}>Carregant…</div>}
          {list.isError && <div className={styles.error}>Error en carregar la llista</div>}
          {list.data && list.data.length === 0 && (
            <div className={styles.muted}>Cap alumne coincidents amb la cerca.</div>
          )}
          {list.data && list.data.length > 0 && (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Cognoms, nom</th>
                  <th>DNI</th>
                  <th>RALC</th>
                  <th>Email</th>
                </tr>
              </thead>
              <tbody>
                {list.data.map(a => (
                  <tr
                    key={a.id}
                    className={selected === a.id ? styles.rowSelected : ""}
                    onClick={() => setSelected(a.id)}
                    onDoubleClick={() => navigate(`/alumnes/${a.id}/expedient`)}
                    title="Doble clic per veure l'expedient"
                  >
                    <td className={styles.name}>
                      <div>{a.cognoms}, {a.nom}</div>
                      {a.data_naixement && (
                        <div className={styles.subText}>{a.data_naixement}</div>
                      )}
                    </td>
                    <td className={styles.mono}>{a.dni ?? "—"}</td>
                    <td className={styles.mono}>{a.ralc}</td>
                    <td>{a.email ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        {selected !== null && (
          <aside className={styles.detail}>
            {detail.isLoading && <div className={styles.muted}>Carregant fitxa…</div>}
            {detail.data && (
              <>
                <header>
                  <p className={styles.eyebrow}>Fitxa d'alumne</p>
                  <h2>
                    {detail.data.nom} {detail.data.cognoms}
                  </h2>
                  <p className={styles.detailSub}>
                    {detail.data.dni && (
                      <>
                        DNI <span className={styles.mono}>{detail.data.dni}</span> ·{" "}
                      </>
                    )}
                    RALC <span className={styles.mono}>{detail.data.ralc}</span>
                  </p>
                </header>

                <div className={styles.section}>
                  <h3>Contacte</h3>
                  <dl className={styles.kv}>
                    <dt>Email</dt>
                    <dd>{detail.data.email ?? "—"}</dd>
                    <dt>Telèfon</dt>
                    <dd className={styles.mono}>{detail.data.telefon ?? "—"}</dd>
                    <dt>Naixement</dt>
                    <dd className={styles.mono}>
                      {detail.data.data_naixement ?? "—"}
                    </dd>
                  </dl>
                </div>

                {detail.data.tutors_legals.length > 0 && (
                  <div className={styles.section}>
                    <h3>Tutors legals ({detail.data.tutors_legals.length})</h3>
                    {detail.data.tutors_legals.map(t => (
                      <div key={t.id} className={styles.tutorRow}>
                        <div>
                          <div className={styles.tutorName}>{t.nom}</div>
                          {t.email && <div className={styles.subText}>{t.email}</div>}
                        </div>
                        {t.telefon && <span className={styles.mono}>{t.telefon}</span>}
                      </div>
                    ))}
                  </div>
                )}

                <div className={styles.actions}>
                  <Button
                    variant="primary"
                    onClick={() => navigate(`/alumnes/${detail.data!.id}/expedient`)}
                  >
                    Veure expedient →
                  </Button>
                  {isAdmin && (
                    <>
                      <Button onClick={() => setFormMode("edit")}>Editar</Button>
                      <span style={{ flex: 1 }} />
                      <Button
                        variant="danger"
                        onClick={() => setConfirmDelete(detail.data!)}
                      >
                        Donar de baixa
                      </Button>
                    </>
                  )}
                </div>
              </>
            )}
          </aside>
        )}
      </div>

      {confirmDelete && (
        <ConfirmDialog
          title="Donar de baixa"
          message={`Donaràs de baixa ${confirmDelete.nom} ${confirmDelete.cognoms} de l'arxiu actiu. Les seves matrícules i qualificacions es preserven (arxiu permanent).`}
          confirmLabel="Donar de baixa"
          variant="danger"
          onConfirm={() => deleteMut.mutate(confirmDelete.id)}
          onClose={() => setConfirmDelete(null)}
        />
      )}

      {formMode && (
        <AlumneFormModal
          alumne={formMode === "edit" ? detail.data ?? null : null}
          onClose={() => setFormMode(null)}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["alumnes"] });
            if (formMode === "edit" && selected !== null) {
              qc.invalidateQueries({ queryKey: ["alumne", selected] });
            }
          }}
        />
      )}
    </div>
  );
}
