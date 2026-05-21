/** Typed client for /stats endpoints. */
import { api } from "./client";

export type HistogramBin = {
  label: string;
  lo: number;
  hi: number;
  count: number;
};

export type RaStat = {
  ra_id: number;
  codi: string;
  descripcio: string;
  pes: number;
  avg: number | null;
  suspesos: number;
  aprovats: number;
  no_qualificats: number;
};

export type ModulStats = {
  modul_id: number;
  grup_id: number;
  avaluacio_id: number;
  n_alumnes: number;
  n_qualificats: number;
  n_complerts: number;
  avg_final: number | null;
  median_final: number | null;
  pct_aprovats: number | null;
  histogram: HistogramBin[];
  ras: RaStat[];
};

export const statsApi = {
  modul: (grupId: number, modulId: number, avaluacioId: number) =>
    api<ModulStats>(
      `/stats/grup/${grupId}/modul/${modulId}/avaluacio/${avaluacioId}`,
    ),
};
