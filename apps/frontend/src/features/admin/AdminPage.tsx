/** Admin — single place to manage Cursos / Grups / Matrícules / Assignacions
 * docents. Admin-only (the route guard enforces it).
 *
 * Tab UX is simpler than spawning four pages. Each tab is self-contained.
 */
import { useState } from "react";

import { AssignacionsTab } from "./AssignacionsTab";
import { CursosTab } from "./CursosTab";
import { EmailTab } from "./EmailTab";
import { FamiliesTab } from "./FamiliesTab";
import { GrupsTab } from "./GrupsTab";
import { MatriculesTab } from "./MatriculesTab";

import styles from "./AdminPage.module.css";

type Tab =
  | "cursos"
  | "families"
  | "grups"
  | "matricules"
  | "assignacions"
  | "email";

const TABS: { id: Tab; label: string; desc: string }[] = [
  { id: "cursos", label: "Cursos acadèmics", desc: "Anys escolars (2025-2026…)" },
  { id: "families", label: "Famílies", desc: "Famílies professionals" },
  { id: "grups", label: "Grups classe", desc: "DAM1A, SMX1A… amb tutor" },
  { id: "matricules", label: "Matrícules", desc: "Inscriure alumnes a grups" },
  { id: "assignacions", label: "Assignacions", desc: "Profes ↔ mòduls ↔ grups" },
  { id: "email", label: "Email", desc: "Configuració SMTP (Gmail…)" },
];

export function AdminPage() {
  const [tab, setTab] = useState<Tab>("cursos");

  return (
    <div className={styles.page}>
      <header className={styles.head}>
        <p className={styles.eyebrow}>Administració · Configuració del sistema</p>
        <h1 className={styles.title}>Gestió del centre</h1>
        <p className={styles.sub}>
          Cursos, grups, matrícules i assignacions docents. Configura aquí l'arquitectura
          d'un curs acadèmic abans de començar la primera avaluació.
        </p>
      </header>

      <nav className={styles.tabs}>
        {TABS.map(t => (
          <button
            key={t.id}
            type="button"
            className={`${styles.tab} ${tab === t.id ? styles.tabActive : ""}`}
            onClick={() => setTab(t.id)}
          >
            <span className={styles.tabLabel}>{t.label}</span>
            <span className={styles.tabDesc}>{t.desc}</span>
          </button>
        ))}
      </nav>

      <section className={styles.tabPanel}>
        {tab === "cursos" && <CursosTab />}
        {tab === "families" && <FamiliesTab />}
        {tab === "grups" && <GrupsTab />}
        {tab === "matricules" && <MatriculesTab />}
        {tab === "assignacions" && <AssignacionsTab />}
        {tab === "email" && <EmailTab />}
      </section>
    </div>
  );
}
