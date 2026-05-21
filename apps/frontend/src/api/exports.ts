/** Export download helpers. Each fn triggers an authenticated GET that returns
 * a binary (xlsx) or csv blob, then drives a hidden <a> click to save it. */
import { apiBaseUrl } from "./client";

async function downloadBlob(path: string, accessToken: string | null): Promise<void> {
  const r = await fetch(`${apiBaseUrl}${path}`, {
    method: "GET",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!r.ok) {
    let msg = `Export failed (${r.status})`;
    try {
      const body = (await r.json()) as { message?: string };
      if (body?.message) msg = body.message;
    } catch {
      // ignore non-JSON
    }
    throw new Error(msg);
  }
  const blob = await r.blob();
  // Prefer the server-provided filename if Content-Disposition is set; else fallback.
  const cd = r.headers.get("Content-Disposition") ?? "";
  const match = /filename="?([^";]+)"?/i.exec(cd);
  const filename = match?.[1] ?? path.split("/").pop() ?? "export";

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const exportsApi = {
  alumne: (id: number, token: string | null) =>
    downloadBlob(`/export/alumne/${id}.xlsx`, token),
  grup: (id: number, token: string | null) =>
    downloadBlob(`/export/grup/${id}.xlsx`, token),
  grupModul: (
    grupId: number,
    modulId: number,
    avaluacioId: number | null,
    token: string | null,
  ) => {
    const qs = avaluacioId !== null ? `?avaluacio_id=${avaluacioId}` : "";
    return downloadBlob(`/export/grup/${grupId}/modul/${modulId}.xlsx${qs}`, token);
  },
  curs: (id: number, token: string | null) =>
    downloadBlob(`/export/curs/${id}.xlsx`, token),
  cicle: (id: number, token: string | null) =>
    downloadBlob(`/export/cicle/${id}.xlsx`, token),
  docent: (id: number, token: string | null) =>
    downloadBlob(`/export/docent/${id}.xlsx`, token),
  audit: (
    params: { user_id?: number; entity?: string; action?: string; limit?: number },
    token: string | null,
  ) => {
    const sp = new URLSearchParams();
    if (params.user_id) sp.set("user_id", String(params.user_id));
    if (params.entity) sp.set("entity", params.entity);
    if (params.action) sp.set("action", params.action);
    if (params.limit) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return downloadBlob(`/export/audit.csv${qs ? `?${qs}` : ""}`, token);
  },
};
