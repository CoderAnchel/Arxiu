/** Typed client for /dashboard. */
import { api } from "./client";

export type DashboardStats = {
  curs_actiu_id: number | null;
  curs_actiu_nom: string | null;
  alumnes_matriculats: number;
  grups_actius: number;
  cicles_actius: number;
  avaluacio_actual: string | null;
  avaluacio_actual_estat: string | null;
  pendents: number;
};

export type ActivityRow = {
  id: number;
  action: string;
  entity: string;
  entity_id: string | null;
  user_id: number | null;
  created_at: string;
};

export type DashboardResponse = {
  stats: DashboardStats;
  recent_activity: ActivityRow[];
};

export type TreeNode = {
  id: number;
  codi: string;
  nom: string;
  nivell: string;
  grups: { id: number; codi: string; curs: number; tutor_user_id: number | null }[];
};

export const dashboardApi = {
  get: () => api<DashboardResponse>("/dashboard"),
  getTree: (curs_acad_id?: number) =>
    api<TreeNode[]>(
      `/dashboard/tree${curs_acad_id !== undefined ? `?curs_acad_id=${curs_acad_id}` : ""}`,
    ),
};
