/** App shell — sidebar (collapsible) + topbar + Cmd+K + main outlet. */
import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { CmdK } from "@/features/cmdk/CmdK";
import { useUIStore } from "@/stores/uiStore";

import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import styles from "./AppShell.module.css";

export function AppShell() {
  const collapsed = useUIStore(s => s.sidebarCollapsed);
  const location = useLocation();
  const [cmdkOpen, setCmdkOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdkOpen(o => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div
      className={`${styles.app} ${collapsed ? styles.collapsed : ""}`}
      data-screen-label={location.pathname}
    >
      <Sidebar />
      <main className={styles.main}>
        <Topbar onOpenCmdK={() => setCmdkOpen(true)} />
        <Outlet />
      </main>
      <CmdK open={cmdkOpen} onClose={() => setCmdkOpen(false)} />
    </div>
  );
}
