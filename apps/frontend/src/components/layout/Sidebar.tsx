/** Sidebar — nav, theme switcher, user card. Mirrors the mockup app.jsx 1:1. */
import { NavLink } from "react-router-dom";

import { Icon, type IconName } from "@/components/ui/Icon";
import { useAuthStore } from "@/stores/authStore";
import { type Theme, useUIStore } from "@/stores/uiStore";

import styles from "./AppShell.module.css";

type NavItem = {
  to: string;
  label: string;
  icon: IconName;
  kbd?: string;
  adminOnly?: boolean;
};
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Navegació",
    items: [
      { to: "/", label: "Arxiu", icon: "archive", kbd: "A" },
      { to: "/qualificacions", label: "Qualificacions", icon: "pencil", kbd: "G" },
      { to: "/avaluacions", label: "Avaluacions", icon: "bookmark", kbd: "E" },
    ],
  },
  {
    label: "Gestió",
    items: [
      { to: "/alumnes", label: "Alumnes", icon: "users" },
      { to: "/curriculums", label: "Currículums", icon: "layers" },
      { to: "/docents", label: "Docents", icon: "user" },
    ],
  },
  {
    label: "Sortides",
    items: [
      { to: "/butlletins", label: "Butlletins", icon: "print" },
      { to: "/enviaments", label: "Enviaments", icon: "mail" },
      { to: "/importacions", label: "Importacions", icon: "upload", adminOnly: true },
    ],
  },
  {
    label: "Administració",
    items: [
      { to: "/administracio", label: "Configuració", icon: "settings", adminOnly: true },
      { to: "/paperera", label: "Paperera", icon: "trash", adminOnly: true },
      { to: "/audit", label: "Auditoria", icon: "history", adminOnly: true },
    ],
  },
];

const THEMES: { value: Theme; label: string; icon: string }[] = [
  { value: "clar", label: "Clar", icon: "☀" },
  { value: "fosc", label: "Fosc", icon: "◑" },
  { value: "editorial", label: "Editorial", icon: "❡" },
];

export function Sidebar() {
  const collapsed = useUIStore(s => s.sidebarCollapsed);
  const theme = useUIStore(s => s.theme);
  const setTheme = useUIStore(s => s.setTheme);
  const toggleSidebar = useUIStore(s => s.toggleSidebar);
  const user = useAuthStore(s => s.user);

  return (
    <aside className={styles.sidebar}>
      <button
        type="button"
        className={styles.collapseBtn}
        onClick={toggleSidebar}
        title={collapsed ? "Expandir" : "Plegar"}
      >
        {collapsed ? "›" : "‹"}
      </button>

      <div className={styles.brand}>
        <span className={styles.brandMark}>A</span>
        <span className={styles.brandTitle}>Arxiu</span>
        <span className={styles.brandSub}>v1.0</span>
      </div>

      <div className={styles.navArea}>
        {NAV_GROUPS.map(group => {
          const visible = group.items.filter(
            item => !item.adminOnly || user?.role === "admin",
          );
          if (visible.length === 0) return null;
          return (
            <div key={group.label} className={styles.navSection}>
              <div className={styles.navLabel}>{group.label}</div>
              {visible.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  title={item.label}
                  className={({ isActive }) =>
                    `${styles.navItem}${isActive ? ` ${styles.active}` : ""}`
                  }
                >
                  <span className={styles.ico}>
                    <Icon name={item.icon} size={15} />
                  </span>
                  <span>{item.label}</span>
                  {item.kbd && <span className={styles.kbd}>{item.kbd}</span>}
                </NavLink>
              ))}
            </div>
          );
        })}
      </div>

      <div className={styles.themeSwitcher}>
        <div className={styles.navLabel}>Aparença</div>
        <div className={styles.themePills}>
          {THEMES.map(t => (
            <button
              key={t.value}
              type="button"
              onClick={() => setTheme(t.value)}
              data-active={theme === t.value}
              className={styles.themePill}
              title={t.label}
            >
              <span className={styles.themePillIcon}>{t.icon}</span>
              <span className={styles.themePillLabel}>{t.label}</span>
            </button>
          ))}
        </div>
      </div>

      {user && (
        <div className={styles.userCard}>
          <div className={styles.userAvatar}>{user.nom[0]}</div>
          <div className={styles.userMeta}>
            <div className={styles.userName}>
              {user.nom} {user.cognoms}
            </div>
            <div className={styles.userRole}>{user.role} · centre</div>
          </div>
        </div>
      )}
    </aside>
  );
}
