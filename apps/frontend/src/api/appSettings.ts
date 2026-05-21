/** Typed client for /settings (admin-only). */
import { api } from "./client";

export type SmtpSettings = {
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_from_email: string | null;
  smtp_from_name: string | null;
  smtp_use_tls: boolean;
  has_password: boolean;
  updated_at: string | null;
  updated_by_user_id: number | null;
};

export type SmtpUpdate = Partial<{
  smtp_host: string;
  smtp_port: number;
  smtp_username: string;
  /** `null` = keep current; `""` = clear; otherwise set new */
  smtp_password: string | null;
  smtp_from_email: string;
  smtp_from_name: string;
  smtp_use_tls: boolean;
}>;

export type SmtpTestRequest = {
  to: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_username?: string;
  smtp_password?: string;
  smtp_from_email?: string;
  smtp_from_name?: string;
  smtp_use_tls?: boolean;
};

export type SmtpTestResponse = { ok: boolean; detail: string };

export const appSettingsApi = {
  getSmtp: () => api<SmtpSettings>("/settings/smtp"),
  updateSmtp: (body: SmtpUpdate) =>
    api<SmtpSettings>("/settings/smtp", { method: "PATCH", body }),
  testSmtp: (body: SmtpTestRequest) =>
    api<SmtpTestResponse>("/settings/smtp/test", { method: "POST", body }),
};
