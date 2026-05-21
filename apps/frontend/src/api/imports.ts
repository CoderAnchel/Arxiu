/** Typed client for /imports + /audit-logs. */
import { api, apiBaseUrl } from "./client";

export type TipusImport = "alumnes" | "matricules" | "notes";
export type EstatImport = "pending" | "processing" | "completed" | "failed";

export type ImportPreviewRow = {
  row: number;
  data: Record<string, unknown>;
  errors: string[];
  warnings: string[];
};

export type ImportRecord = {
  id: number;
  tipus: TipusImport;
  fitxer_nom: string | null;
  user_id: number | null;
  total: number;
  ok: number;
  errors: number;
  estat: EstatImport;
  created_at: string;
  completed_at: string | null;
};

export type ImportPreview = ImportRecord & {
  preview: ImportPreviewRow[];
};

export type ImportConfirm = ImportRecord & {
  result: {
    created: number;
    updated: number;
    errors: number;
    error_rows: { row: number; errors: string[] }[];
  } | null;
};

export type AuditLog = {
  id: number;
  user_id: number | null;
  action: string;
  entity: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

async function _uploadImport(
  path: string,
  fd: FormData,
  accessToken: string | null,
): Promise<ImportPreview> {
  const r = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    body: fd,
  });
  if (!r.ok) {
    let body: { error?: string; message?: string } | null = null;
    try {
      body = (await r.json()) as typeof body;
    } catch {
      // ignore
    }
    const err = new Error(body?.message ?? `Upload failed (${r.status})`);
    (err as { code?: string; status?: number }).code = body?.error;
    (err as { code?: string; status?: number }).status = r.status;
    throw err;
  }
  return r.json() as Promise<ImportPreview>;
}

export const importsApi = {
  list: () => api<ImportRecord[]>("/imports"),
  get: (id: number) => api<ImportPreview>(`/imports/${id}`),

  uploadAlumnes: (file: File, accessToken: string | null): Promise<ImportPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    return _uploadImport(`/imports/alumnes`, fd, accessToken);
  },

  uploadNotes: (
    file: File,
    modulId: number,
    avaluacioId: number,
    accessToken: string | null,
  ): Promise<ImportPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("modul_id", String(modulId));
    fd.append("avaluacio_id", String(avaluacioId));
    return _uploadImport(`/imports/notes`, fd, accessToken);
  },

  confirm: (id: number) => api<ImportConfirm>(`/imports/${id}/confirm`, { method: "POST" }),

  listAuditLogs: (params?: {
    user_id?: number;
    entity?: string;
    action?: string;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.user_id) sp.set("user_id", String(params.user_id));
    if (params?.entity) sp.set("entity", params.entity);
    if (params?.action) sp.set("action", params.action);
    if (params?.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return api<AuditLog[]>(`/audit-logs${qs ? `?${qs}` : ""}`);
  },
};
