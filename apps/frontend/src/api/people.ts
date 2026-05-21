/** Typed client for /alumnes etc. */
import { api } from "./client";

export type Alumne = {
  id: number;
  dni: string | null;
  ralc: string;
  nom: string;
  cognoms: string;
  email: string | null;
  telefon: string | null;
  data_naixement: string | null;
  tutors_legals: TutorLegal[];
};

export type TutorLegal = {
  id: number;
  nom: string;
  email: string | null;
  telefon: string | null;
};

export type AlumneCreate = {
  dni?: string | null;
  ralc: string;
  nom: string;
  cognoms: string;
  email?: string | null;
  telefon?: string | null;
  data_naixement?: string | null;
  tutors_legals?: { nom: string; email?: string | null; telefon?: string | null }[];
};

export const peopleApi = {
  listAlumnes: (params?: { q?: string; limit?: number; offset?: number }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    const qs = sp.toString();
    return api<Alumne[]>(`/alumnes${qs ? `?${qs}` : ""}`);
  },
  getAlumne: (id: number) => api<Alumne>(`/alumnes/${id}`),
  createAlumne: (body: AlumneCreate) =>
    api<Alumne>("/alumnes", { method: "POST", body }),
  updateAlumne: (id: number, body: Partial<AlumneCreate>) =>
    api<Alumne>(`/alumnes/${id}`, { method: "PATCH", body }),
  deleteAlumne: (id: number) => api<void>(`/alumnes/${id}`, { method: "DELETE" }),
};
