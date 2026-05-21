/** Enviaments — tracking table with filters + detail + resend. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiError } from "@/api/client";
import { outputsApi, type Enviament, type EstatEnviament } from "@/api/outputs";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useAuthStore } from "@/stores/authStore";
import { toast } from "@/stores/toastStore";

import styles from "./EnviamentsPage.module.css";

const ESTAT_OPTIONS: (EstatEnviament | "tots")[] = [
  "tots",
  "enviat",
  "obert",
  "rebotat",
  "error",
  "queued",
];

export function EnviamentsPage() {
  const qc = useQueryClient();
  const role = useAuthStore(s => s.user?.role ?? null);
  const isAdmin = role === "admin";
  const [filter, setFilter] = useState<EstatEnviament | "tots">("tots");
  const [detail, setDetail] = useState<Enviament | null>(null);

  const list = useQuery({
    queryKey: ["enviaments", filter],
    queryFn: () =>
      outputsApi.listEnviaments({
        ...(filter !== "tots" ? { estat: filter as EstatEnviament } : {}),
        limit: 200,
      }),
  });

  const resendMut = useMutation({
    mutationFn: (id: number) => outputsApi.resendEnviament(id),
    onSuccess: updated => {
      qc.invalidateQueries({ queryKey: ["enviaments"] });
      setDetail(updated);
      toast.success(`Reenviament processat (${updated.estat})`);
    },
    onError: (err: ApiError) => {
      const msg =
        err.code === "not_resendable"
          ? "Aquest enviament no es pot reenviar (només s'admeten els d'estat error/rebotat)"
          : err.code === "permission_denied"
            ? "Només l'admin pot reenviar"
            : err.message || "Error en reenviar";
      toast.error(msg);
    },
  });

  const counts = (list.data ?? []).reduce<Record<string, number>>((acc, e) => {
    acc[e.estat] = (acc[e.estat] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Sortides · Comunicacions per email</p>
        <h1 className={styles.title}>Enviaments</h1>
        <p className={styles.sub}>
          Registre complet d'emails enviats. Tracking d'estat (enviat / obert / rebotat
          / error) i reenviament dels que han fallat.
        </p>
      </header>

      <div className={styles.stats}>
        <Stat label="Enviats" value={counts.enviat ?? 0} accent="info" />
        <Stat label="Oberts" value={counts.obert ?? 0} accent="green" />
        <Stat label="Rebotats" value={counts.rebotat ?? 0} accent="warn" />
        <Stat label="Errors" value={counts.error ?? 0} accent="danger" />
      </div>

      <div className={styles.toolbar}>
        <div className={styles.chips}>
          {ESTAT_OPTIONS.map(o => (
            <button
              key={o}
              type="button"
              className={`${styles.chip} ${filter === o ? styles.chipActive : ""}`}
              onClick={() => setFilter(o)}
            >
              {o}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.tableWrap}>
        {list.isLoading && <p className={styles.muted}>Carregant…</p>}
        {list.data && list.data.length === 0 && (
          <p className={styles.muted}>Cap enviament en aquest filtre.</p>
        )}
        {list.data && list.data.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Data</th>
                <th>Destinatari</th>
                <th>Assumpte</th>
                <th>Tipus</th>
                <th>Estat</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map(e => (
                <tr key={e.id}>
                  <td className={styles.mono}>
                    {new Date(e.queued_at).toLocaleString("ca-ES", {
                      day: "2-digit",
                      month: "short",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className={styles.mono}>{e.destinatari_email}</td>
                  <td>{e.assumpte}</td>
                  <td>
                    <span className={styles.tag}>{e.tipus}</span>
                  </td>
                  <td>
                    <span className={`${styles.estatTag} ${styles[`estat_${e.estat}`]}`}>
                      {e.estat}
                    </span>
                  </td>
                  <td>
                    <Button size="sm" variant="ghost" onClick={() => setDetail(e)}>
                      Veure →
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detail && (
        <Modal
          title={detail.assumpte}
          subtitle={`#${detail.id} · ${detail.destinatari_email}`}
          onClose={() => setDetail(null)}
          maxWidth={520}
          footer={
            <>
              <Button onClick={() => setDetail(null)}>Tancar</Button>
              {isAdmin &&
                (detail.estat === "error" || detail.estat === "rebotat") && (
                  <Button
                    variant="primary"
                    disabled={resendMut.isPending}
                    onClick={() => resendMut.mutate(detail.id)}
                  >
                    {resendMut.isPending ? "Reenviant…" : "Reenviar"}
                  </Button>
                )}
            </>
          }
        >
          <dl className={styles.kv}>
            <dt>Estat</dt>
            <dd>
              <span className={`${styles.estatTag} ${styles[`estat_${detail.estat}`]}`}>
                {detail.estat}
              </span>
            </dd>
            <dt>Encolat</dt>
            <dd className={styles.mono}>
              {new Date(detail.queued_at).toLocaleString("ca-ES")}
            </dd>
            {detail.sent_at && (
              <>
                <dt>Enviat</dt>
                <dd className={styles.mono}>
                  {new Date(detail.sent_at).toLocaleString("ca-ES")}
                </dd>
              </>
            )}
            {detail.opened_at && (
              <>
                <dt>Obert</dt>
                <dd className={styles.mono}>
                  {new Date(detail.opened_at).toLocaleString("ca-ES")}
                </dd>
              </>
            )}
            {detail.adjunt_filename && (
              <>
                <dt>Adjunt</dt>
                <dd className={styles.mono}>{detail.adjunt_filename}</dd>
              </>
            )}
            {detail.error_msg && (
              <>
                <dt>Error</dt>
                <dd className={styles.errorMsg}>{detail.error_msg}</dd>
              </>
            )}
          </dl>
        </Modal>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent: "info" | "green" | "warn" | "danger";
}) {
  return (
    <div className={styles.statCard}>
      <div className={styles.statLabel}>{label}</div>
      <div className={`${styles.statValue} ${styles[`accent_${accent}`]}`}>{value}</div>
    </div>
  );
}
