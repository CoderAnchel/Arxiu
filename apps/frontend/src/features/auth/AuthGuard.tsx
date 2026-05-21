/** Wrap protected routes so unauthenticated users are bounced to /login.
 *
 *  - Status `loading`            → render nothing (avoid login flicker on refresh)
 *  - `anonymous`                 → redirect to /login
 *  - `must_change_password`      → redirect to /change-password
 *  - `authenticated`             → render children, optionally enforcing role
 */
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import type { Role } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export function AuthGuard({
  children,
  requireRole,
}: {
  children: ReactNode;
  requireRole?: Role;
}) {
  const status = useAuthStore(s => s.status);
  const user = useAuthStore(s => s.user);
  const location = useLocation();

  if (status === "loading") return null;

  if (status === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (status === "must_change_password") {
    return <Navigate to="/change-password" replace />;
  }

  if (requireRole && user?.role !== requireRole) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
