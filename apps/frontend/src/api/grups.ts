/** Typed client for grups + matrícules + assignacions docents endpoints. */
import { api } from "./client";

export type Grup = {
  id: number;
  codi: string;
  curs_acad_id: number;
  cicle_id: number;
  curs: number;
  tutor_user_id: number | null;
  cicle_codi?: string | null;
  curs_acad_nom?: string | null;
  tutor_nom_complet?: string | null;
};

export type GrupCreate = {
  codi: string;
  curs_acad_id: number;
  cicle_id: number;
  curs: number;
  tutor_user_id?: number | null;
};

export type Matricula = {
  id: number;
  alumne_id: number;
  grup_id: number;
  cicle_id: number;
  curs: number;
  curs_acad_id: number;
  tipus: "primari" | "secundari";
  estat: "actiu" | "finalitzat" | "baixa";
};

export type MatriculaCreate = Omit<Matricula, "id">;

export type AssignacioDocent = {
  id: number;
  user_id: number;
  grup_id: number;
  modul_id: number;
  curs_acad_id: number;
};

export type AssignacioDocentCreate = Omit<AssignacioDocent, "id">;

export const grupsApi = {
  list: (curs_acad_id?: number) =>
    api<Grup[]>(
      `/grups${curs_acad_id !== undefined ? `?curs_acad_id=${curs_acad_id}` : ""}`,
    ),
  create: (body: GrupCreate) => api<Grup>("/grups", { method: "POST", body }),
  update: (id: number, body: Partial<GrupCreate>) =>
    api<Grup>(`/grups/${id}`, { method: "PATCH", body }),
};

export const matriculesApi = {
  list: (params?: { curs_acad_id?: number; grup_id?: number; alumne_id?: number }) => {
    const sp = new URLSearchParams();
    if (params?.curs_acad_id) sp.set("curs_acad_id", String(params.curs_acad_id));
    if (params?.grup_id) sp.set("grup_id", String(params.grup_id));
    if (params?.alumne_id) sp.set("alumne_id", String(params.alumne_id));
    const qs = sp.toString();
    return api<Matricula[]>(`/matricules${qs ? `?${qs}` : ""}`);
  },
  create: (body: MatriculaCreate) =>
    api<Matricula>("/matricules", { method: "POST", body }),
  update: (
    id: number,
    body: Partial<Pick<MatriculaCreate, "grup_id" | "estat">>,
  ) => api<Matricula>(`/matricules/${id}`, { method: "PATCH", body }),
};

export const assignacionsApi = {
  list: (params?: { user_id?: number; grup_id?: number; curs_acad_id?: number }) => {
    const sp = new URLSearchParams();
    if (params?.user_id) sp.set("user_id", String(params.user_id));
    if (params?.grup_id) sp.set("grup_id", String(params.grup_id));
    if (params?.curs_acad_id) sp.set("curs_acad_id", String(params.curs_acad_id));
    const qs = sp.toString();
    return api<AssignacioDocent[]>(`/assignacions-docents${qs ? `?${qs}` : ""}`);
  },
  create: (body: AssignacioDocentCreate) =>
    api<AssignacioDocent>("/assignacions-docents", { method: "POST", body }),
  delete: (id: number) =>
    api<void>(`/assignacions-docents/${id}`, { method: "DELETE" }),
};
