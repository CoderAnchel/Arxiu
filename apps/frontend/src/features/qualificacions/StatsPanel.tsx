/** Stats panel — histogram + KPIs + per-RA breakdown.
 *
 * Renders inline at QualifsPage when the user clicks "Veure estadístiques".
 * Histogram is hand-drawn SVG (10 buckets) — no charting library needed.
 */
import { useQuery } from "@tanstack/react-query";

import { statsApi, type ModulStats } from "@/api/stats";

import styles from "./StatsPanel.module.css";

export function StatsPanel({
  grupId,
  modulId,
  avaluacioId,
}: {
  grupId: number;
  modulId: number;
  avaluacioId: number;
}) {
  const q = useQuery({
    queryKey: ["stats", grupId, modulId, avaluacioId],
    queryFn: () => statsApi.modul(grupId, modulId, avaluacioId),
  });

  if (q.isLoading) return <p className={styles.muted}>Calculant estadístiques…</p>;
  if (q.isError || !q.data) return <p className={styles.muted}>No s'han pogut carregar les estadístiques.</p>;
  const s = q.data;

  return (
    <section className={styles.panel}>
      <header className={styles.panelHead}>
        <span className={styles.eyebrow}>Estadístiques · Mòdul</span>
        <h3 className={styles.title}>Distribució de notes finals</h3>
      </header>

      <div className={styles.kpis}>
        <Kpi label="Alumnes" value={s.n_alumnes} />
        <Kpi label="Qualificats" value={s.n_qualificats} sub={`/ ${s.n_alumnes}`} />
        <Kpi
          label="Mitjana"
          value={s.avg_final !== null ? s.avg_final.toFixed(2) : "—"}
          variant={s.avg_final !== null && s.avg_final < 5 ? "warn" : "ok"}
        />
        <Kpi
          label="Mediana"
          value={s.median_final !== null ? s.median_final.toFixed(2) : "—"}
        />
        <Kpi
          label="% Aprovats"
          value={s.pct_aprovats !== null ? `${s.pct_aprovats}%` : "—"}
          variant={
            s.pct_aprovats === null
              ? "default"
              : s.pct_aprovats >= 70
              ? "ok"
              : s.pct_aprovats >= 50
              ? "warn"
              : "danger"
          }
        />
      </div>

      <Histogram bins={s.histogram} />

      <div className={styles.raBlock}>
        <h4 className={styles.subTitle}>Per resultat d'aprenentatge</h4>
        {s.ras.length === 0 && (
          <p className={styles.muted}>El mòdul no té cap RA definit.</p>
        )}
        {s.ras.length > 0 && (
          <table className={styles.raTable}>
            <thead>
              <tr>
                <th>RA</th>
                <th>Pes</th>
                <th>Mitjana</th>
                <th>Aprovats</th>
                <th>Suspesos</th>
                <th>NQ</th>
              </tr>
            </thead>
            <tbody>
              {s.ras.map(r => (
                <tr key={r.ra_id}>
                  <td>
                    <strong>{r.codi}</strong>
                    <span className={styles.raDesc}>{r.descripcio}</span>
                  </td>
                  <td className={styles.mono}>{r.pes}%</td>
                  <td className={styles.mono}>
                    {r.avg !== null ? r.avg.toFixed(2) : "—"}
                  </td>
                  <td>
                    <span className={`${styles.pill} ${styles.pillOk}`}>
                      {r.aprovats}
                    </span>
                  </td>
                  <td>
                    {r.suspesos > 0 ? (
                      <span className={`${styles.pill} ${styles.pillBad}`}>
                        {r.suspesos}
                      </span>
                    ) : (
                      <span className={styles.mono}>0</span>
                    )}
                  </td>
                  <td className={styles.mono}>{r.no_qualificats}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function Kpi({
  label,
  value,
  sub,
  variant = "default",
}: {
  label: string;
  value: number | string;
  sub?: string;
  variant?: "default" | "ok" | "warn" | "danger";
}) {
  return (
    <div className={`${styles.kpi} ${styles[`kpi_${variant}`]}`}>
      <div className={styles.kpiLabel}>{label}</div>
      <div className={styles.kpiValue}>
        {value}
        {sub && <span className={styles.kpiSub}>{sub}</span>}
      </div>
    </div>
  );
}

function Histogram({ bins }: { bins: ModulStats["histogram"] }) {
  const w = 720;
  const h = 220;
  const padL = 32;
  const padR = 12;
  const padT = 16;
  const padB = 38;
  const innerW = w - padL - padR;
  const innerH = h - padT - padB;
  const max = Math.max(1, ...bins.map(b => b.count));
  const barW = innerW / bins.length;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={styles.svg}>
      {/* Y axis ticks at 0, max */}
      <line
        x1={padL}
        y1={padT}
        x2={padL}
        y2={padT + innerH}
        stroke="var(--line)"
      />
      <line
        x1={padL}
        y1={padT + innerH}
        x2={padL + innerW}
        y2={padT + innerH}
        stroke="var(--line)"
      />
      <text x={padL - 8} y={padT + 4} className={styles.axisText} textAnchor="end">
        {max}
      </text>
      <text
        x={padL - 8}
        y={padT + innerH}
        className={styles.axisText}
        textAnchor="end"
      >
        0
      </text>

      {/* Threshold line at the boundary between fail (5) and pass */}
      {(() => {
        // bin labels are 0-2, 2-3, … 5-6, …, find index where lo == 5
        const idx = bins.findIndex(b => b.lo === 5);
        if (idx < 0) return null;
        const x = padL + idx * barW;
        return (
          <line
            x1={x}
            y1={padT}
            x2={x}
            y2={padT + innerH}
            stroke="var(--danger)"
            strokeDasharray="4 3"
            opacity={0.5}
          />
        );
      })()}

      {bins.map((b, i) => {
        const barH = (b.count / max) * innerH;
        const x = padL + i * barW + 4;
        const y = padT + innerH - barH;
        const fail = b.lo < 5;
        return (
          <g key={b.label}>
            <rect
              x={x}
              y={y}
              width={barW - 8}
              height={barH}
              fill={fail ? "var(--danger)" : "var(--accent)"}
              opacity={0.75}
            />
            {b.count > 0 && (
              <text
                x={x + (barW - 8) / 2}
                y={y - 4}
                className={styles.axisText}
                textAnchor="middle"
              >
                {b.count}
              </text>
            )}
            <text
              x={x + (barW - 8) / 2}
              y={padT + innerH + 16}
              className={styles.tickText}
              textAnchor="middle"
            >
              {b.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
