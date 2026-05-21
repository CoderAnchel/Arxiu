/** Typed client for admin user management. */
import { api, apiBaseUrl } from "./client";
import type { Role } from "./auth";

export type AdminUser = {
  id: number;
  dni: string;
  email: string;
  nom: string;
  cognoms: string;
  departament: string | null;
  role: Role;
  active: boolean;
  must_change_password: boolean;
  has_oauth_linked: boolean;
  has_mfa: boolean;
  last_login_at: string | null;
  created_at: string;
};

export type AdminUserCreate = {
  dni: string;
  email: string;
  nom: string;
  cognoms: string;
  role: Role;
  departament?: string | null;
};

export type AdminUserUpdate = Partial<{
  email: string;
  nom: string;
  cognoms: string;
  departament: string | null;
  role: Role;
  active: boolean;
}>;

export type AdminUserCreated = AdminUser & { generated_password: string };

export const adminApi = {
  list: () => api<AdminUser[]>("/admin/users"),
  create: (body: AdminUserCreate) =>
    api<AdminUserCreated>("/admin/users", { method: "POST", body }),
  update: (id: number, body: AdminUserUpdate) =>
    api<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body }),
  delete: (id: number) => api<void>(`/admin/users/${id}`, { method: "DELETE" }),
  regeneratePassword: (id: number) =>
    api<{ user_id: number; generated_password: string }>(
      `/admin/users/${id}/regenerate-password`,
      { method: "POST" },
    ),
  emailPassword: (id: number) =>
    api<void>(`/admin/users/${id}/email-password`, { method: "POST" }),

  /** Triggers a CSV download with regenerated passwords for the given users.
   * Uses fetch directly so we get the raw blob; the JSON variant is
   * available at /bulk-generate-passwords/json if a structured response
   * is needed instead. */
  bulkGeneratePasswordsCsv: async (
    userIds: number[],
    accessToken: string | null,
  ): Promise<void> => {
    const r = await fetch(`${apiBaseUrl}/admin/users/bulk-generate-passwords`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ user_ids: userIds }),
    });
    if (!r.ok) {
      throw new Error(`Bulk regen failed (${r.status})`);
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "arxiu-credencials.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
