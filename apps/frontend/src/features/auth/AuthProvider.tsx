/** AuthProvider — bootstraps auth state on app mount and wires the api client.
 *
 * On mount: try `POST /auth/refresh` (the HttpOnly refresh cookie may already
 * exist from a previous session). On success, fetch /auth/me and mark
 * authenticated. On failure, mark anonymous.
 */
import { useEffect, type ReactNode } from "react";

import { authApi } from "@/api/auth";
import { configureClient } from "@/api/client";
import { useAuthStore } from "@/stores/authStore";

export function AuthProvider({ children }: { children: ReactNode }) {
  const setAccessToken = useAuthStore(s => s.setAccessToken);
  const setUser = useAuthStore(s => s.setUser);
  const setStatus = useAuthStore(s => s.setStatus);
  const reset = useAuthStore(s => s.reset);

  useEffect(() => {
    configureClient({
      getAccessToken: () => useAuthStore.getState().accessToken,
      setAccessToken: t => useAuthStore.getState().setAccessToken(t),
      onAuthLost: () => useAuthStore.getState().reset(),
    });

    let cancelled = false;
    (async () => {
      try {
        const refreshed = await authApi.refresh();
        if (cancelled) return;
        setAccessToken(refreshed.access_token);
        const me = await authApi.me();
        if (cancelled) return;
        setUser(me);
        setStatus(me.must_change_password ? "must_change_password" : "authenticated");
      } catch {
        if (!cancelled) reset();
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [reset, setAccessToken, setStatus, setUser]);

  return <>{children}</>;
}
