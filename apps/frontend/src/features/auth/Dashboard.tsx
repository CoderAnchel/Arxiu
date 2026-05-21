/** Phase 1 placeholder dashboard — replaced in Phase 2 by the real Sidebar + Topbar
 * + page routes from the mockup. For now: prove that a logged-in user can see
 * their /me payload and log out. */
import { useNavigate } from "react-router-dom";

import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export function Dashboard() {
  const user = useAuthStore(s => s.user);
  const reset = useAuthStore(s => s.reset);
  const navigate = useNavigate();

  if (!user) return null;

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
    <main className="phase0-shell">
      <header>
        <span className="brand-mark">A</span>
        <div>
          <h1>Has entrat a l'Arxiu</h1>
          <p className="eyebrow">Phase 1 dashboard placeholder</p>
        </div>
      </header>

      <section className="status-card">
        <h2>El teu compte</h2>
        <dl className="status ok">
          <dt>Nom</dt>
          <dd>
            {user.nom} {user.cognoms}
          </dd>
          <dt>DNI</dt>
          <dd>{user.dni}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Rol</dt>
          <dd>{user.role}</dd>
          {user.departament && (
            <>
              <dt>Departament</dt>
              <dd>{user.departament}</dd>
            </>
          )}
          <dt>2FA</dt>
          <dd>{user.has_mfa ? "activat" : "no activat"}</dd>
          <dt>Google</dt>
          <dd>{user.has_oauth_linked ? "vinculat" : "no vinculat"}</dd>
        </dl>
      </section>

      <footer>
        <button
          type="button"
          onClick={handleLogout}
          style={{
            padding: "8px 14px",
            border: "1px solid var(--line)",
            background: "var(--bg-2)",
            color: "var(--ink)",
            borderRadius: "var(--r)",
            cursor: "pointer",
          }}
        >
          Sortir
        </button>
        <p style={{ marginTop: 16 }}>
          Phase 2 (catàleg + persones) substituirà aquesta pantalla pel sidebar real i les
          pàgines del mockup connectades a l'API.
        </p>
      </footer>
    </main>
  );
}
