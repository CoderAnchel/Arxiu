/** Grup expedient — historical view of a class.
 * Route: /grups/:id/expedient
 *
 * Shows: which curs acadèmic, cicle, curs, tutor, and the full list of alumnes
 * with their estat de matrícula. Each alumne is a link to their own expedient.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { downloadActa } from "@/api/acta";
import { archiveApi } from "@/api/archive";
import { authApi } from "@/api/auth";
import { exportsApi } from "@/api/exports";
import { gradingApi, type Avaluacio } from "@/api/grading";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { Modal } from "@/components/ui/Modal";
import { useExport } from "@/hooks/useExport";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./GrupExpedientPage.module.css";

export function GrupExpedientPage() {
  const { id } = useParams<{ id: string }>();
  const grupId = id ? Number(id) : null;
  const navigate = useNavigate();

  const exp = useQuery({
    queryKey: ["grup-expedient", grupId],
    queryFn: () => archiveApi.grupExpedient(grupId!),
    enabled: grupId !== null,
  });
  const exporter = useExport();
  const accessToken = useAuthStore(s => s.accessToken);
  const isAdmin = useAuthStore(s => s.user?.role === "admin");
  const myAssigs = useQuery({
    queryKey: ["my-assignacions"],
    queryFn: () => authApi.myAssignacions(),
    enabled: !isAdmin,
  });
  const [actaOpen, setActaOpen] = useState(false);

  if (exp.isLoading) {
    return (
      <div className={styles.page}>
        <p className={styles.muted}>Carregant grup…</p>
      </div>
    );
  }
  if (exp.isError || !exp.data) {
    return (
      <div className={styles.page}>
        <p className={styles.error}>No s'ha pogut carregar el grup.</p>
        <Button onClick={() => navigate(-1)}>← Tornar</Button>
      </div>
    );
  }

  const g = exp.data;
  // Has this user any relationship with the grup? Same rule as the backend:
  // admin always; tutor of grup; docent assigned to any modul of grup.
  const isTutorOfGrup =
    myAssigs.data?.tutorships?.includes(g.grup_id) ?? false;
  const hasAssignacioInGrup =
    myAssigs.data?.assignacions?.some(a => a.grup_id === g.grup_id) ?? false;
  const canAccessGrup = isAdmin || isTutorOfGrup || hasAssignacioInGrup;
  // Sending butlletins emails: admin or tutor (no other docent).
  const canSendButlletins = isAdmin || isTutorOfGrup;
  const counts = g.alumnes.reduce<Record<string, number>>((acc, a) => {
    acc[a.estat] = (acc[a.estat] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>
          Grup classe · curs {g.curs_acad_nom}
        </p>
        <h1 className={styles.title}>{g.grup_codi}</h1>
        <p className={styles.sub}>
          {g.cicle_codi} · {g.cicle_nom} · {g.curs}r curs · {g.cicle_nivell}
        </p>
        <div className={styles.tags}>
          {g.tutor_nom_complet && g.tutor_user_id ? (
            <Link
              to={`/docents?selected=${g.tutor_user_id}`}
              className={`${styles.tag} ${styles.tagLink}`}
              title="Veure fitxa del docent"
            >
              Tutor/a: <strong>{g.tutor_nom_complet}</strong>
            </Link>
          ) : g.tutor_nom_complet ? (
            <span className={styles.tag}>
              Tutor/a: <strong>{g.tutor_nom_complet}</strong>
            </span>
          ) : (
            <span className={`${styles.tag} ${styles.tagWarn}`}>Sense tutor assignat</span>
          )}
          <span className={styles.tag}>
            <strong>{g.alumnes.length}</strong> alumnes
          </span>
          {(["actiu", "finalitzat", "baixa"] as const).map(s =>
            counts[s] ? (
              <span key={s} className={`${styles.tag} ${styles[`tag_${s}`]}`}>
                {counts[s]} {s}
              </span>
            ) : null,
          )}
        </div>
        <div className={styles.actions}>
          <Button onClick={() => navigate(-1)}>← Tornar</Button>
          <Button
            variant="primary"
            onClick={() =>
              navigate(`/qualificacions?curs=${g.curs_acad_id}&grup=${g.grup_id}`)
            }
          >
            Veure qualificacions
          </Button>
          {canSendButlletins && (
            <Button
              onClick={() =>
                navigate(`/butlletins?curs=${g.curs_acad_id}&grup=${g.grup_id}`)
              }
            >
              Generar butlletins
            </Button>
          )}
          {canAccessGrup && (
            <Button
              disabled={exporter.exporting}
              onClick={() => exporter.run(t => exportsApi.grup(g.grup_id, t), "Grup")}
            >
              {exporter.exporting ? "Exportant…" : "⬇ Exportar XLSX"}
            </Button>
          )}
          {canAccessGrup && (
            <Button
              variant="primary"
              onClick={() => setActaOpen(true)}
              title="Generar Acta de Junta d'Avaluació"
            >
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Icon name="actaPdf" size={14} />
                Acta de Junta
              </span>
            </Button>
          )}
        </div>
      </header>

      <section className={styles.card}>
        <div className={styles.cardHead}>
          Alumnes matriculats · {g.alumnes.length}
        </div>
        {g.alumnes.length === 0 && (
          <p className={styles.muted}>Cap alumne matriculat en aquest grup.</p>
        )}
        {g.alumnes.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Alumne</th>
                <th>DNI</th>
                <th>RALC</th>
                <th>Estat matrícula</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {g.alumnes.map(a => (
                <tr key={a.matricula_id}>
                  <td className={styles.name}>
                    {a.cognoms}, {a.nom}
                  </td>
                  <td className={styles.mono}>{a.dni ?? "—"}</td>
                  <td className={styles.mono}>{a.ralc}</td>
                  <td>
                    <span className={`${styles.estatTag} ${styles[`estat_${a.estat}`]}`}>
                      {a.estat}
                    </span>
                  </td>
                  <td>
                    <Link
                      to={`/alumnes/${a.alumne_id}/expedient`}
                      className={styles.link}
                    >
                      Veure expedient →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {actaOpen && (
        <ActaModal
          grupId={g.grup_id}
          cursAcadId={g.curs_acad_id}
          tutorDefault={g.tutor_nom_complet ?? ""}
          accessToken={accessToken}
          onClose={() => setActaOpen(false)}
        />
      )}
    </div>
  );
}

function ActaModal({
  grupId,
  cursAcadId,
  tutorDefault,
  accessToken,
  onClose,
}: {
  grupId: number;
  cursAcadId: number;
  tutorDefault: string;
  accessToken: string | null;
  onClose: () => void;
}) {
  const avals = useQuery({
    queryKey: ["avaluacions", cursAcadId],
    queryFn: () => gradingApi.listAvaluacions(cursAcadId),
  });
  const [avalId, setAvalId] = useState<number | null>(null);
  const [tutorSig, setTutorSig] = useState(tutorDefault);
  const [capSig, setCapSig] = useState("");
  const [dirSig, setDirSig] = useState("");
  const [running, setRunning] = useState(false);

  // Pick most-advanced aval by default (preferring junta/tancada)
  const defaultAval = (avals.data ?? []).find(
    a => a.estat === "junta" || a.estat === "tancada",
  ) ?? avals.data?.[0];
  if (avalId === null && defaultAval) {
    setAvalId(defaultAval.id);
  }

  const handle = async () => {
    if (avalId === null) return;
    setRunning(true);
    try {
      await downloadActa(grupId, avalId, accessToken, {
        tutor_signat: tutorSig || undefined,
        cap_estudis_signat: capSig || undefined,
        director_signat: dirSig || undefined,
      });
      toast.success("Acta generada");
      onClose();
    } catch (err) {
      toast.error((err as Error).message || "No s'ha pogut generar l'acta");
    } finally {
      setRunning(false);
    }
  };

  return (
    <Modal
      title="Generar Acta de Junta d'Avaluació"
      onClose={() => !running && onClose()}
      maxWidth={520}
      footer={
        <>
          <Button onClick={onClose} disabled={running}>
            Cancel·lar
          </Button>
          <Button
            variant="primary"
            disabled={running || avalId === null}
            onClick={handle}
          >
            {running ? "Generant…" : "Descarregar PDF"}
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ink-3)" }}>
            Avaluació
          </span>
          <select
            value={avalId ?? ""}
            onChange={e => setAvalId(Number(e.target.value))}
            style={{ padding: "8px 12px", borderRadius: "var(--r)", border: "1px solid var(--line)", background: "var(--bg-2)" }}
          >
            {(avals.data ?? []).map((a: Avaluacio) => (
              <option key={a.id} value={a.id}>
                {a.nom} · {a.estat}
              </option>
            ))}
          </select>
        </label>
        <p style={{ margin: 0, fontSize: 12, color: "var(--ink-3)" }}>
          Noms per a les signatures (apareixeran impresos sota la línia, no
          substitueixen la signatura manuscrita).
        </p>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ink-3)" }}>
            Tutor/a
          </span>
          <input
            value={tutorSig}
            onChange={e => setTutorSig(e.target.value)}
            placeholder="Nom complet"
            style={{ padding: "8px 12px", borderRadius: "var(--r)", border: "1px solid var(--line)", background: "var(--bg-2)" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ink-3)" }}>
            Cap d'estudis
          </span>
          <input
            value={capSig}
            onChange={e => setCapSig(e.target.value)}
            placeholder="Nom complet"
            style={{ padding: "8px 12px", borderRadius: "var(--r)", border: "1px solid var(--line)", background: "var(--bg-2)" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ fontFamily: "var(--mono)", fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--ink-3)" }}>
            Director/a
          </span>
          <input
            value={dirSig}
            onChange={e => setDirSig(e.target.value)}
            placeholder="Nom complet"
            style={{ padding: "8px 12px", borderRadius: "var(--r)", border: "1px solid var(--line)", background: "var(--bg-2)" }}
          />
        </label>
      </div>
    </Modal>
  );
}
