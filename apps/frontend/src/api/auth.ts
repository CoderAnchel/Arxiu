/** Typed auth endpoints. Eventually replaced by codegen from /openapi.json. */
import { api } from "./client";

export type Role = "admin" | "professor";

export type LoginRequest = {
  identifier: string;
  password: string;
  totp_code?: string;
};

export type LoginResponse = {
  access_token: string | null;
  password_change_token: string | null;
  must_change_password: boolean;
  token_type: "Bearer";
  expires_in: number;
  role: Role;
  user_id: number;
};

export type Me = {
  id: number;
  dni: string;
  email: string;
  nom: string;
  cognoms: string;
  departament: string | null;
  role: Role;
  active: boolean;
  must_change_password: boolean;
  has_mfa: boolean;
  has_oauth_linked: boolean;
};

export type AssignacioRow = {
  grup_id: number;
  modul_id: number;
  curs_acad_id: number;
  grup_codi: string | null;
  is_tutor: boolean;
};

export type MyAssignacions = {
  role: Role;
  assignacions: AssignacioRow[];
  tutorships: number[];
};

export const authApi = {
  login: (body: LoginRequest) =>
    api<LoginResponse>("/auth/login", { method: "POST", body, anonymous: true }),

  changePassword: (body: { current_password: string; new_password: string }, token?: string) =>
    api<void>("/auth/change-password", {
      method: "POST",
      body,
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      anonymous: !!token,
    }),

  refresh: () => api<{ access_token: string; expires_in: number }>("/auth/refresh", { method: "POST" }),

  logout: () => api<void>("/auth/logout", { method: "POST" }),

  me: () => api<Me>("/auth/me"),

  myAssignacions: () => api<MyAssignacions>("/auth/me/assignacions"),
};
