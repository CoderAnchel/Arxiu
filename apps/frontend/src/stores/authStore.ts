/** Auth state — access token (in memory) + current user. Refresh token lives in
 * an HttpOnly cookie set by the backend, untouched by JS. */
import { create } from "zustand";

import type { Me, Role } from "@/api/auth";

type AuthStatus = "loading" | "anonymous" | "must_change_password" | "authenticated";

type AuthState = {
  status: AuthStatus;
  accessToken: string | null;
  passwordChangeToken: string | null;
  user: Me | null;
  setAccessToken: (t: string | null) => void;
  setPasswordChangeToken: (t: string | null) => void;
  setUser: (u: Me | null) => void;
  setStatus: (s: AuthStatus) => void;
  reset: () => void;
};

export const useAuthStore = create<AuthState>(set => ({
  status: "loading",
  accessToken: null,
  passwordChangeToken: null,
  user: null,
  setAccessToken: t => set({ accessToken: t }),
  setPasswordChangeToken: t => set({ passwordChangeToken: t }),
  setUser: u => set({ user: u }),
  setStatus: s => set({ status: s }),
  reset: () =>
    set({
      status: "anonymous",
      accessToken: null,
      passwordChangeToken: null,
      user: null,
    }),
}));

export const authSelectors = {
  isAuthenticated: (s: AuthState): boolean => s.status === "authenticated",
  role: (s: AuthState): Role | null => s.user?.role ?? null,
};
