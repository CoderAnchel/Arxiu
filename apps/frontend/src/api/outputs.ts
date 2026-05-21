/** Typed client for /butlletins and /enviaments. */
import { api, apiBaseUrl } from "./client";

export type ButlletiOpts = {
  detall_ra: boolean;
  comentaris: boolean;
  distribucio_grup: boolean;
  signatura: boolean;
  logo_centre: boolean;
};

export const DEFAULT_OPTS: ButlletiOpts = {
  detall_ra: true,
  comentaris: true,
  distribucio_grup: false,
  signatura: true,
  logo_centre: true,
};

export type EstatEnviament = "queued" | "enviat" | "obert" | "rebotat" | "error";

export type Enviament = {
  id: number;
  alumne_id: number | null;
  destinatari_email: string;
  tipus: "butlleti" | "comunicat" | "recordatori" | "credencials";
  assumpte: string;
  estat: EstatEnviament;
  error_msg: string | null;
  queued_at: string;
  sent_at: string | null;
  opened_at: string | null;
  avaluacio_id: number | null;
  adjunt_filename: string | null;
};

export type ButlletiSendResult = {
  alumne_id: number;
  destinatari_email: string;
  enviament_id: number;
  estat: EstatEnviament;
  error: string | null;
};

export type ButlletiSendResponse = {
  results: ButlletiSendResult[];
  sent: number;
  failed: number;
};

/** Fetch a PDF as a Blob (uses Bearer auth via the api client). */
async function fetchPdfBlob(url: string, accessToken: string | null): Promise<Blob> {
  const r = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!r.ok) throw new Error(`pdf fetch failed: ${r.status}`);
  return r.blob();
}

export const outputsApi = {
  /** Returns an object URL for an iframe; caller is responsible for revoking it. */
  previewUrl: async (alumneId: number, avaluacioId: number, accessToken: string | null) => {
    const blob = await fetchPdfBlob(
      `${apiBaseUrl}/butlletins/preview/${alumneId}/${avaluacioId}`,
      accessToken,
    );
    return URL.createObjectURL(blob);
  },

  /** Generate PDFs for the selection. Returns a Blob (ZIP) on success. */
  generateZip: async (
    avaluacioId: number,
    alumneIds: number[],
    opts: ButlletiOpts,
    accessToken: string | null,
  ): Promise<{ blob: Blob; filename: string; generated: number; failed: number }> => {
    const r = await fetch(`${apiBaseUrl}/butlletins/generate`, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/zip, application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ avaluacio_id: avaluacioId, alumne_ids: alumneIds, opts }),
    });
    if (!r.ok) throw new Error(`generate failed: ${r.status}`);
    const blob = await r.blob();
    const cd = r.headers.get("content-disposition") ?? "";
    const m = /filename="([^"]+)"/.exec(cd);
    return {
      blob,
      filename: m?.[1] ?? "butlletins.zip",
      generated: Number(r.headers.get("x-generated") ?? "0"),
      failed: Number(r.headers.get("x-failed") ?? "0"),
    };
  },

  send: (avaluacioId: number, alumneIds: number[], sendTo: string[], opts: ButlletiOpts) =>
    api<ButlletiSendResponse>("/enviaments/butlletins", {
      method: "POST",
      body: { avaluacio_id: avaluacioId, alumne_ids: alumneIds, send_to: sendTo, opts },
    }),

  listEnviaments: (params?: {
    estat?: EstatEnviament;
    alumne_id?: number;
    avaluacio_id?: number;
    limit?: number;
    offset?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.estat) sp.set("estat", params.estat);
    if (params?.alumne_id) sp.set("alumne_id", String(params.alumne_id));
    if (params?.avaluacio_id) sp.set("avaluacio_id", String(params.avaluacio_id));
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    const qs = sp.toString();
    return api<Enviament[]>(`/enviaments${qs ? `?${qs}` : ""}`);
  },

  resendEnviament: (id: number) =>
    api<Enviament>(`/enviaments/${id}/resend`, { method: "POST" }),
};
