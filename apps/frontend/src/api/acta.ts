/** Acta de Junta — PDF download client. */
import { apiBaseUrl } from "./client";

export async function downloadActa(
  grupId: number,
  avaluacioId: number,
  accessToken: string | null,
  opts?: {
    tutor_signat?: string;
    cap_estudis_signat?: string;
    director_signat?: string;
  },
): Promise<void> {
  const sp = new URLSearchParams();
  if (opts?.tutor_signat) sp.set("tutor_signat", opts.tutor_signat);
  if (opts?.cap_estudis_signat) sp.set("cap_estudis_signat", opts.cap_estudis_signat);
  if (opts?.director_signat) sp.set("director_signat", opts.director_signat);
  const qs = sp.toString();
  const url = `${apiBaseUrl}/acta/grup/${grupId}/avaluacio/${avaluacioId}.pdf${qs ? `?${qs}` : ""}`;

  const r = await fetch(url, {
    method: "GET",
    credentials: "include",
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!r.ok) {
    let msg = `Acta failed (${r.status})`;
    try {
      const body = (await r.json()) as { message?: string };
      if (body?.message) msg = body.message;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  const blob = await r.blob();
  const cd = r.headers.get("Content-Disposition") ?? "";
  const m = /filename="?([^";]+)"?/i.exec(cd);
  const filename = m?.[1] ?? `acta_${grupId}_${avaluacioId}.pdf`;

  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}
