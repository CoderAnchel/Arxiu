/** Alumne expedient — full academic history across all cursos acadèmics.
 * Route: /alumnes/:id/expedient
 */
import { useQuery } from "@tanstack/react-query";
import { useParams, useNavigate, Link } from "react-router-dom";

import { archiveApi } from "@/api/archive";
import { exportsApi } from "@/api/exports";
import { Button } from "@/components/ui/Button";
import { useExport } from "@/hooks/useExport";

import styles from "./AlumneExpedientPage.module.css";

export function AlumneExpedientPage() {
  const { id } = useParams<{ id: string }>();
  const alumneId = id ? Number(id) : null;
  const navigate = useNavigate();

  const exp = useQuery({
    queryKey: ["alumne-expedient", alumneId],
    queryFn: () => archiveApi.alumneExpedient(alumneId!),
    enabled: alumneId !== null,
  });

  const exporter = useExport();

  if (exp.isLoading) {
    return <div className={styles.page}><p className={styles.muted}>Carregant expedient…</p></div>;
  }
  if (exp.isError || !exp.data) {
    return (
      <div className={styles.page}>
        <p className={styles.error}>No s'ha pogut carregar l'expedient.</p>
        <Button onClick={() => navigate(-1)}>← Tornar</Button>
      </div>
    );
  }

  const { alumne, tutors_legals, matricules } = exp.data;
  const fullName = `${alumne.cognoms}, ${alumne.nom}`;

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>
          Expedient acadèmic · {matricules.length}{" "}
          {matricules.length === 1 ? "matrícula" : "matrícules"}
        </p>
        <h1 className={styles.title}>{fullName}</h1>
        <p className={styles.sub}>
          DNI <span className={styles.mono}>{alumne.dni ?? "—"}</span> · RALC{" "}
          <span className={styles.mono}>{alumne.ralc}</span>
          {alumne.data_naixement && (
            <>
              {" · "}Naixement <span className={styles.mono}>{alumne.data_naixement}</span>
            </>
          )}
        </p>
        <div className={styles.actions}>
          <Button onClick={() => navigate(`/alumnes?selected=${alumne.id}`)}>
            ← Tornar a Alumnes
          </Button>
          <Button
            disabled={exporter.exporting}
            onClick={() =>
              exporter.run(t => exportsApi.alumne(alumne.id, t), "Expedient")
            }
          >
            {exporter.exporting ? "Exportant…" : "⬇ Exportar XLSX"}
          </Button>
        </div>
      </header>

      {/* Contacte + tutors */}
      <section className={styles.card}>
        <div className={styles.cardHead}>Contacte</div>
        <dl className={styles.kv}>
          <dt>Email</dt>
          <dd>{alumne.email ?? "—"}</dd>
          <dt>Telèfon</dt>
          <dd className={styles.mono}>{alumne.telefon ?? "—"}</dd>
        </dl>
        {tutors_legals.length > 0 && (
          <div className={styles.tutorsSection}>
            <div className={styles.cardHead} style={{ borderTop: "1px solid var(--line-soft)" }}>
              Tutors legals
            </div>
            {tutors_legals.map(t => (
              <div key={t.id} className={styles.tutorRow}>
                <div className={styles.tutorNom}>{t.nom}</div>
                <div className={styles.mono}>{t.email ?? "—"}</div>
                <div className={styles.mono}>{t.telefon ?? "—"}</div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Trajectory — one section per matricula */}
      {matricules.length === 0 && (
        <section className={styles.card}>
          <div className={styles.cardHead}>Trajectòria</div>
          <p className={styles.muted}>Cap matrícula registrada.</p>
        </section>
      )}

      {matricules.map(matr => (
        <section key={matr.matricula_id} className={styles.card}>
          <div className={styles.matrHead}>
            <div>
              <div className={styles.matrCurs}>{matr.curs_acad_nom}</div>
              <h2 className={styles.matrTitle}>
                {matr.cicle_codi} · {matr.curs}r curs
                <span className={styles.tag}>{matr.estat}</span>
              </h2>
              <p className={styles.matrSub}>
                {matr.cicle_nom} · grup{" "}
                <Link to={`/grups/${matr.grup_id}/expedient`} className={styles.link}>
                  {matr.grup_codi}
                </Link>
                {matr.tipus !== "primari" && (
                  <span className={styles.tag}>{matr.tipus}</span>
                )}
              </p>
            </div>
          </div>

          {matr.moduls.length === 0 && (
            <p className={styles.muted}>Cap mòdul registrat per a aquesta matrícula.</p>
          )}

          {matr.moduls.map(mod => (
            <div key={mod.modul_id} className={styles.modulBlock}>
              <div className={styles.modulHead}>
                <span className={styles.mono}>{mod.modul_codi}</span>
                <span className={styles.modulNom}>{mod.modul_nom}</span>
                <span className={styles.tagSm}>{mod.ras.length} RA</span>
              </div>

              {mod.ras.length > 0 && (
                <div className={styles.notesGrid}>
                  <table className={styles.notesTable}>
                    <thead>
                      <tr>
                        <th>RA</th>
                        {mod.avaluacions.map(a => (
                          <th key={a.avaluacio_id} className={styles.colNum}>
                            {a.avaluacio_nom}
                            <span className={styles.estat}>{a.avaluacio_estat}</span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {mod.ras.map(r => (
                        <tr key={r.id}>
                          <td>
                            <div className={styles.raCodi}>{r.codi}</div>
                            <div className={styles.raDesc} title={r.descripcio}>
                              {r.descripcio}
                            </div>
                          </td>
                          {mod.avaluacions.map(a => {
                            const n = a.notes[r.codi];
                            return (
                              <td key={a.avaluacio_id} className={styles.colNum}>
                                <span className={`${styles.num} ${classForNota(n)}`}>
                                  {n === null || n === undefined ? "—" : n.toFixed(1)}
                                </span>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                      <tr className={styles.summaryRow}>
                        <td>Mitjana del mòdul</td>
                        {mod.avaluacions.map(a => (
                          <td key={a.avaluacio_id} className={styles.colNum}>
                            <span
                              className={`${styles.num} ${classForNota(a.mitjana_modul)}`}
                            >
                              {a.mitjana_modul === null
                                ? "—"
                                : a.mitjana_modul.toFixed(2)}
                            </span>
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function classForNota(n: number | null | undefined): string {
  if (n === null || n === undefined) return styles.numEmpty!;
  if (n < 5) return styles.numSusp!;
  if (n >= 9) return styles.numExc!;
  return styles.numApr!;
}
