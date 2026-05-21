/** Typed API for catalog endpoints. */
import { api } from "./client";

export type Nivell = "mig" | "superior";

export type Familia = { id: number; codi: string; nom: string };

export type Cicle = {
  id: number;
  codi: string;
  nom: string;
  familia_id: number | null;
  nivell: Nivell;
  durada: number;
  // Política de junta del cicle (per al càlcul automàtic de decisió)
  max_suspesos_recupera: number;
  pct_hores_no_promociona: string | null; // Decimal serialitzat com a string
};

export type Modul = {
  id: number;
  cicle_id: number;
  codi: string;
  nom: string;
  curs: number;
  hores: number;
  bloquejant: boolean;
  ras: Ra[];
};

export type Ra = {
  id: number;
  modul_id: number;
  ordre: number;
  codi: string;
  descripcio: string;
  pes: string; // Pydantic Decimal serialises as string
};

export type CicleDetail = Cicle & { moduls: Modul[] };

export type CursAcademic = {
  id: number;
  nom: string;
  actiu: boolean;
  data_inici: string | null;
  data_fi: string | null;
};

export type CursAcademicCreate = {
  nom: string;
  actiu?: boolean;
  data_inici?: string | null;
  data_fi?: string | null;
};

export const catalogApi = {
  // Cicles
  listCicles: () => api<Cicle[]>("/cicles"),
  getCicle: (id: number) => api<CicleDetail>(`/cicles/${id}`),
  createCicle: (body: Omit<Cicle, "id">) => api<Cicle>("/cicles", { method: "POST", body }),
  updateCicle: (id: number, body: Partial<Omit<Cicle, "id">>) =>
    api<Cicle>(`/cicles/${id}`, { method: "PATCH", body }),
  deleteCicle: (id: number) => api<void>(`/cicles/${id}`, { method: "DELETE" }),

  // Mòduls
  listModuls: (cicleId?: number) =>
    api<Modul[]>(`/moduls${cicleId !== undefined ? `?cicle_id=${cicleId}` : ""}`),
  createModul: (body: Omit<Modul, "id" | "ras">) => api<Modul>("/moduls", { method: "POST", body }),
  updateModul: (id: number, body: Partial<Omit<Modul, "id" | "ras" | "cicle_id">>) =>
    api<Modul>(`/moduls/${id}`, { method: "PATCH", body }),
  deleteModul: (id: number) => api<void>(`/moduls/${id}`, { method: "DELETE" }),

  // RAs
  listRas: (modulId: number) => api<Ra[]>(`/moduls/${modulId}/ras`),
  createRa: (body: { modul_id: number; ordre: number; codi: string; descripcio: string; pes: number | string }) =>
    api<Ra>("/ras", { method: "POST", body }),
  updateRa: (id: number, body: Partial<{ ordre: number; codi: string; descripcio: string; pes: number | string }>) =>
    api<Ra>(`/ras/${id}`, { method: "PATCH", body }),
  deleteRa: (id: number) => api<void>(`/ras/${id}`, { method: "DELETE" }),

  // Famílies
  listFamilies: () => api<Familia[]>("/families"),
  createFamilia: (body: { codi: string; nom: string }) =>
    api<Familia>("/families", { method: "POST", body }),
  updateFamilia: (id: number, body: Partial<{ codi: string; nom: string }>) =>
    api<Familia>(`/families/${id}`, { method: "PATCH", body }),
  deleteFamilia: (id: number) => api<void>(`/families/${id}`, { method: "DELETE" }),

  // Cursos acadèmics
  listCursos: () => api<CursAcademic[]>("/cursos-academics"),
  getCursActiu: () => api<CursAcademic | null>("/cursos-academics/active"),
  createCurs: (body: CursAcademicCreate) =>
    api<CursAcademic>("/cursos-academics", { method: "POST", body }),
  updateCurs: (id: number, body: Partial<CursAcademicCreate>) =>
    api<CursAcademic>(`/cursos-academics/${id}`, { method: "PATCH", body }),
  cloneCurs: (
    sourceId: number,
    body: {
      nom: string;
      set_active?: boolean;
      clone_grups?: boolean;
      clone_assignacions?: boolean;
      data_inici?: string | null;
      data_fi?: string | null;
    },
  ) =>
    api<CursAcademic>(`/cursos-academics/${sourceId}/clone`, {
      method: "POST",
      body,
    }),
};
