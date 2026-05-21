/** Arxiu — the home of the archive.
 *
 * This is what makes the system an "Arxiu" (archive): you can pick ANY curs
 * acadèmic (past, present, future) and browse its structure — cicles, grups,
 * alumnes. The active curs is highlighted but you're never forced into it.
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────────────────────┐
 *   │ Eyebrow · CURS [select ▾]                                            │
 *   │ Arxiu de notes — title                                               │
 *   │ [stat] [stat] [stat] [stat]                                          │
 *   ├────────────────────────────┬─────────────────────────────────────────┤
 *   │ Estructura del curs        │ Cerca a l'arxiu                          │
 *   │ (cicles → grups, click)    │ [input  ] hits…                          │
 *   │                            ├─────────────────────────────────────────┤
 *   │                            │ Activitat recent                         │
 *   └────────────────────────────┴─────────────────────────────────────────┘
 */
import { useQuery } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { archiveApi } from "@/api/archive";
import { catalogApi, type CursAcademic } from "@/api/catalog";
import { dashboardApi } from "@/api/dashboard";
import { exportsApi } from "@/api/exports";
import { Button } from "@/components/ui/Button";
import { Icon } from "@/components/ui/Icon";
import { useExport } from "@/hooks/useExport";
import { useAuthStore } from "@/stores/authStore";

import styles from "./OverviewPage.module.css";

export function OverviewPage() {
  const navigate = useNavigate();
  const role = useAuthStore(s => s.user?.role);
  const isAdmin = role === "admin";
  const exporter = useExport();

  // --- Curs acadèmic selector (any year) ---------------------------------
  const cursos = useQuery({ queryKey: ["cursos"], queryFn: () => catalogApi.listCursos() });
  const [cursId, setCursId] = useState<number | null>(null);
  useEffect(() => {
    if (cursId !== null) return;
    // Default = active curs, else most recent
    const actiu = cursos.data?.find((c: CursAcademic) => c.actiu) ?? cursos.data?.[0];
    if (actiu) setCursId(actiu.id);
  }, [cursId, cursos.data]);

  const currentCurs = cursos.data?.find(c => c.id === cursId) ?? null;

  // --- Dashboard (stats + activity) — always for active curs --------------
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: () => dashboardApi.get() });
  const stats = dashboard.data?.stats;

  // --- Tree for the *selected* curs (not necessarily active) --------------
  const tree = useQuery({
    queryKey: ["dashboard-tree", cursId],
    queryFn: () => dashboardApi.getTree(cursId ?? undefined),
    enabled: cursId !== null,
  });

  // Tree-only inline filter (separate from the cross-archive search). Prunes
  // cicles + grups matching the typed text. Cicle stays visible if either the
  // cicle itself matches or any of its grups match.
  const [treeFilter, setTreeFilter] = useState("");
  const treeFilterTrim = treeFilter.trim().toLowerCase();
  const filteredTree = useMemo(() => {
    if (!tree.data) return [];
    if (treeFilterTrim.length === 0) return tree.data;
    return tree.data
      .map(cicle => {
        const cicleHit =
          cicle.codi.toLowerCase().includes(treeFilterTrim) ||
          cicle.nom.toLowerCase().includes(treeFilterTrim);
        const matchingGrups = cicle.grups.filter(g =>
          g.codi.toLowerCase().includes(treeFilterTrim),
        );
        if (cicleHit) return cicle;
        if (matchingGrups.length > 0) return { ...cicle, grups: matchingGrups };
        return null;
      })
      .filter((c): c is NonNullable<typeof c> => c !== null);
  }, [tree.data, treeFilterTrim]);

  // --- Cross-archive search ----------------------------------------------
  const [q, setQ] = useState("");
  const dq = useDeferredValue(q);
  const trimmed = dq.trim();
  const search = useQuery({
    queryKey: ["archive-search", trimmed],
    queryFn: () => archiveApi.search(trimmed),
    enabled: trimmed.length >= 2,
  });

  const handleHit = (kind: string, id: number) => {
    if (kind === "alumne") navigate(`/alumnes/${id}/expedient`);
    else if (kind === "grup") navigate(`/grups/${id}/expedient`);
    else if (kind === "cicle") navigate(`/curriculums?cicle=${id}`);
  };

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <div className={styles.eyebrowRow}>
          <span className={styles.eyebrow}>Arxiu · Institut la Ferreria</span>
          <span className={styles.dot}>·</span>
          <label className={styles.cursPicker}>
            <span className={styles.cursLabel}>Curs acadèmic</span>
            <select
              value={cursId ?? ""}
              onChange={e => setCursId(Number(e.target.value))}
              className={styles.cursSelect}
            >
              {(cursos.data ?? []).map(c => (
                <option key={c.id} value={c.id}>
                  {c.nom}
                  {c.actiu ? " · actiu" : ""}
                </option>
              ))}
            </select>
          </label>
        </div>
        <h1 className={styles.title}>Arxiu de notes</h1>
        <p className={styles.sub}>
          Explora qualsevol curs acadèmic — present o passat. Tota la informació
          es preserva: matrícules, qualificacions, butlletins enviats, professors
          assignats. Tria un curs, navega per la seva estructura, o busca per
          DNI, RALC, nom o codi de grup ("DAM1A 2024").
        </p>
        {isAdmin && cursId !== null && (
          <div style={{ marginTop: 12 }}>
            <Button
              disabled={exporter.exporting}
              onClick={() =>
                exporter.run(t => exportsApi.curs(cursId, t), `Curs ${currentCurs?.nom ?? ""}`)
              }
            >
              {exporter.exporting ? "Exportant…" : `⬇ Exportar resum del curs ${currentCurs?.nom ?? ""}`}
            </Button>
          </div>
        )}
      </header>

      {/* --- Stat grid (only for active curs) ------------------------------ */}
      <div className={styles.statGrid}>
        <StatCard
          label="Alumnes matriculats"
          value={stats?.alumnes_matriculats ?? 0}
          trend={stats?.curs_actiu_nom ? `Actiu · ${stats.curs_actiu_nom}` : "—"}
        />
        <StatCard
          label="Grups classe"
          value={stats?.grups_actius ?? 0}
          trend={`${stats?.cicles_actius ?? 0} cicles`}
        />
        <StatCard
          label="Avaluació en curs"
          value={stats?.avaluacio_actual ?? "—"}
          trend={stats?.avaluacio_actual_estat ?? "cap"}
          variantTrend={stats?.avaluacio_actual_estat === "junta" ? "warn" : "default"}
          big={false}
        />
        <StatCard
          label="Pendents"
          value={stats?.pendents ?? 0}
          trend="qualif. per validar"
        />
      </div>

      {/* --- Search bar (full width) --------------------------------------- */}
      <div className={styles.searchBar}>
        <Icon name="search" size={16} />
        <input
          type="search"
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder={"Cerca a l'arxiu — DNI, RALC, nom, codi de grup (\"DAM1A 2024\"), cicle…"}
          className={styles.searchInput}
        />
        <span className={styles.searchHint}>cerca en TOTS els cursos acadèmics</span>
      </div>

      {trimmed.length >= 2 && (
        <div className={styles.searchResults}>
          {search.isLoading && <p className={styles.muted}>Cercant…</p>}
          {search.data && search.data.length === 0 && (
            <p className={styles.muted}>Cap resultat per "{trimmed}"</p>
          )}
          {(search.data ?? []).map(hit => (
            <button
              key={`${hit.kind}-${hit.id}`}
              type="button"
              className={styles.hitRow}
              onClick={() => handleHit(hit.kind, hit.id)}
            >
              <span className={`${styles.kindTag} ${styles[`kind_${hit.kind}`]}`}>
                {hit.kind}
              </span>
              <span className={styles.hitLabel}>{hit.label}</span>
              {hit.sub && <span className={styles.hitSub}>{hit.sub}</span>}
              <span className={styles.go}>→</span>
            </button>
          ))}
        </div>
      )}

      {/* --- Tree + activity ----------------------------------------------- */}
      <div className={styles.layout}>
        <section className={styles.card}>
          <div className={styles.cardHead}>
            <span>Estructura · {currentCurs?.nom ?? "—"}</span>
            <span className={styles.muted}>cicle → grup</span>
          </div>
          <div className={styles.treeFilter}>
            <Icon name="search" size={13} />
            <input
              type="search"
              value={treeFilter}
              onChange={e => setTreeFilter(e.target.value)}
              placeholder="Filtra cicles i grups d'aquest curs…"
              className={styles.treeFilterInput}
            />
            {treeFilter.length > 0 && (
              <button
                type="button"
                className={styles.treeFilterClear}
                onClick={() => setTreeFilter("")}
                title="Esborrar filtre"
              >
                ×
              </button>
            )}
          </div>
          {tree.isLoading && <div className={styles.muted}>Carregant…</div>}
          {tree.data && tree.data.length === 0 && (
            <div className={styles.muted}>
              Cap cicle ni grup registrat per a {currentCurs?.nom ?? "aquest curs"}.
            </div>
          )}
          {tree.data &&
            tree.data.length > 0 &&
            filteredTree.length === 0 &&
            treeFilterTrim.length > 0 && (
              <div className={styles.muted}>
                Cap cicle o grup coincideix amb "{treeFilter}".
              </div>
            )}
          {filteredTree.map(cicle => (
            <div key={cicle.id} className={styles.cicleBlock}>
              <div className={styles.cicleHead}>
                <span className={styles.mono}>{cicle.codi}</span>
                <span className={styles.cicleNom}>{cicle.nom}</span>
                <span className={styles.tag}>{cicle.nivell}</span>
              </div>
              {cicle.grups.map(g => (
                <button
                  key={g.id}
                  type="button"
                  className={styles.grupRow}
                  onClick={() => navigate(`/grups/${g.id}/expedient`)}
                  title={`Veure expedient del grup ${g.codi}`}
                >
                  <Icon name="users" size={13} />
                  <span className={styles.grupCodi}>{g.codi}</span>
                  <span className={styles.grupCurs}>{g.curs}r curs</span>
                  <span className={styles.go}>→</span>
                </button>
              ))}
            </div>
          ))}
        </section>

        <section className={styles.card}>
          <div className={styles.cardHead}>
            <span>Activitat recent</span>
            <span className={styles.muted}>tots els cursos</span>
          </div>
          {dashboard.isLoading && <div className={styles.muted}>Carregant…</div>}
          {dashboard.data && dashboard.data.recent_activity.length === 0 && (
            <div className={styles.muted}>Encara no hi ha activitat registrada.</div>
          )}
          <div className={styles.feed}>
            {dashboard.data?.recent_activity.map(row => (
              <div key={row.id} className={styles.feedRow}>
                <span className={styles.feedDate}>
                  {new Date(row.created_at).toLocaleString("ca-ES", {
                    day: "2-digit",
                    month: "short",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
                <span className={styles.feedAction}>{row.action}</span>
                <span className={styles.feedEntity}>
                  {row.entity}
                  {row.entity_id && (
                    <span className={styles.feedEntityId}> #{row.entity_id}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  trend,
  variantTrend = "default",
  big = true,
}: {
  label: string;
  value: number | string;
  trend?: string;
  variantTrend?: "default" | "warn";
  big?: boolean;
}) {
  return (
    <div className={styles.stat}>
      <div className={styles.statLabel}>{label}</div>
      <div className={`${styles.statValue} ${big ? "" : styles.statValueSmall}`}>{value}</div>
      {trend && (
        <div className={`${styles.statTrend} ${variantTrend === "warn" ? styles.warn : ""}`}>
          {trend}
        </div>
      )}
    </div>
  );
}
