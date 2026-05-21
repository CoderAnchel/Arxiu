/** Audit log viewer — admin-only, paginated table with filters + JSON detail. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { exportsApi } from "@/api/exports";
import { importsApi, type AuditLog } from "@/api/imports";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { useExport } from "@/hooks/useExport";

import styles from "./AuditPage.module.css";

export function AuditPage() {
  const [entity, setEntity] = useState<string>("");
  const [action, setAction] = useState<string>("");
  const [detail, setDetail] = useState<AuditLog | null>(null);
  const exporter = useExport();

  const list = useQuery({
    queryKey: ["audit-logs", entity, action],
    queryFn: () =>
      importsApi.listAuditLogs({
        ...(entity ? { entity } : {}),
        ...(action ? { action } : {}),
        limit: 200,
      }),
  });

  const entities = Array.from(new Set((list.data ?? []).map(r => r.entity))).sort();
  const actions = Array.from(new Set((list.data ?? []).map(r => r.action))).sort();

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Auditoria · Arxiu permanent</p>
        <h1 className={styles.title}>Log d'auditoria</h1>
        <p className={styles.sub}>
          Append-only. Cada canvi a notes, transicions d'avaluació, imports, generació
          de butlletins, regeneració de contrasenyes — tot queda registrat. No es pot
          esborrar.
        </p>
      </header>

      <div className={styles.filters}>
        <label className={styles.select}>
          <span>Entitat</span>
          <select value={entity} onChange={e => setEntity(e.target.value)}>
            <option value="">— totes —</option>
            {entities.map(en => (
              <option key={en} value={en}>
                {en}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.select}>
          <span>Acció</span>
          <select value={action} onChange={e => setAction(e.target.value)}>
            <option value="">— totes —</option>
            {actions.map(a => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </label>
        <span style={{ flex: 1 }} />
        <span className={styles.count}>{list.data?.length ?? 0} esdeveniments</span>
        <Button
          disabled={exporter.exporting}
          onClick={() =>
            exporter.run(
              t =>
                exportsApi.audit(
                  {
                    ...(entity ? { entity } : {}),
                    ...(action ? { action } : {}),
                    limit: 5000,
                  },
                  t,
                ),
              "Auditoria",
            )
          }
        >
          {exporter.exporting ? "Exportant…" : "⬇ Exportar CSV"}
        </Button>
      </div>

      <div className={styles.tableWrap}>
        {list.isLoading && <p className={styles.muted}>Carregant…</p>}
        {list.data && list.data.length === 0 && (
          <p className={styles.muted}>Cap esdeveniment amb aquests filtres.</p>
        )}
        {list.data && list.data.length > 0 && (
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Quan</th>
                <th>Usuari</th>
                <th>Acció</th>
                <th>Entitat</th>
                <th>ID</th>
                <th>IP</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.data.map(row => (
                <tr key={row.id}>
                  <td className={styles.mono}>
                    {new Date(row.created_at).toLocaleString("ca-ES", {
                      day: "2-digit",
                      month: "short",
                      year: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                  <td className={styles.mono}>{row.user_id ?? "—"}</td>
                  <td>
                    <span className={styles.actionTag}>{row.action}</span>
                  </td>
                  <td>{row.entity}</td>
                  <td className={styles.mono}>{row.entity_id ?? "—"}</td>
                  <td className={styles.mono}>{row.ip ?? "—"}</td>
                  <td>
                    {(row.before || row.after) && (
                      <button
                        type="button"
                        className={styles.linkBtn}
                        onClick={() => setDetail(row)}
                      >
                        veure diff →
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {detail && (
        <Modal
          title={`${detail.action} · ${detail.entity}${detail.entity_id ? ` #${detail.entity_id}` : ""}`}
          subtitle={new Date(detail.created_at).toLocaleString("ca-ES")}
          onClose={() => setDetail(null)}
          maxWidth={640}
        >
          {detail.before && (
            <>
              <h4 className={styles.diffHead}>Abans</h4>
              <pre className={styles.diff}>{JSON.stringify(detail.before, null, 2)}</pre>
            </>
          )}
          {detail.after && (
            <>
              <h4 className={styles.diffHead}>Després</h4>
              <pre className={styles.diff}>{JSON.stringify(detail.after, null, 2)}</pre>
            </>
          )}
          <div className={styles.metaGrid}>
            {detail.user_id !== null && (
              <>
                <dt>Usuari</dt>
                <dd className={styles.mono}>#{detail.user_id}</dd>
              </>
            )}
            {detail.ip && (
              <>
                <dt>IP</dt>
                <dd className={styles.mono}>{detail.ip}</dd>
              </>
            )}
            {detail.user_agent && (
              <>
                <dt>User-Agent</dt>
                <dd className={styles.mono}>{detail.user_agent}</dd>
              </>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
