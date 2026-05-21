/** Topbar — breadcrumbs + Cmd+K trigger + logout. */
import { useLocation, useNavigate } from "react-router-dom";

import { authApi } from "@/api/auth";
import { Icon } from "@/components/ui/Icon";
import { useAuthStore } from "@/stores/authStore";

import styles from "./AppShell.module.css";

const PAGE_TITLES: Record<string, string> = {
  "/": "Visió general",
  "/qualificacions": "Qualificacions",
  "/avaluacions": "Avaluacions",
  "/alumnes": "Alumnes",
  "/curriculums": "Currículums",
  "/docents": "Docents",
  "/butlletins": "Butlletins",
  "/enviaments": "Enviaments",
  "/importacions": "Importacions",
  "/audit": "Auditoria",
};

export function Topbar({ onOpenCmdK }: { onOpenCmdK: () => void }) {
  const location = useLocation();
  const navigate = useNavigate();
  const reset = useAuthStore(s => s.reset);
  const title = PAGE_TITLES[location.pathname] ?? "Pàgina";
  const isMac = typeof navigator !== "undefined" && /mac/i.test(navigator.platform);

  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch {
      /* ignore */
    }
    reset();
    navigate("/login", { replace: true });
  };

  return (
    <div className={styles.topbar}>
      <div className={styles.crumbs}>
        <span className={styles.home}>Arxiu</span>
        <span className={styles.sep}>/</span>
        <span className={styles.now}>{title}</span>
      </div>
      <div className={styles.spacer} />
      <button
        type="button"
        className={styles.searchTrigger}
        onClick={onOpenCmdK}
        title="Cerca global"
      >
        <Icon name="search" size={14} />
        <span className={styles.searchLbl}>Cerca alumnes, grups, pàgines…</span>
        <span className={styles.searchKbd}>{isMac ? "⌘ K" : "Ctrl K"}</span>
      </button>
      <button type="button" className={styles.btn} onClick={handleLogout}>
        Sortir
      </button>
    </div>
  );
}
