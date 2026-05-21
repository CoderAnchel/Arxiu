/** Typed client for /archive — historical / search endpoints. */
import { api } from "./client";

export type AlumneSummary = {
  id: number;
  dni: string | null;
  ralc: string;
  nom: string;
  cognoms: string;
  email: string | null;
  telefon: string | null;
  data_naixement: string | null;
};

export type TutorLegalRow = {
  id: number;
  nom: string;
  email: string | null;
  telefon: string | null;
};

export type AvaluacioNotaRow = {
  avaluacio_id: number;
  avaluacio_nom: string;
  avaluacio_estat: string;
  avaluacio_ordre: number;
  notes: Record<string, number | null>;
  mitjana_modul: number | null;
};

export type ModulHistRow = {
  modul_id: number;
  modul_codi: string;
  modul_nom: string;
  curs: number;
  ras: {
    id: number;
    codi: string;
    ordre: number;
    descripcio: string;
    pes: number;
  }[];
  avaluacions: AvaluacioNotaRow[];
};

export type MatriculaHistRow = {
  matricula_id: number;
  curs_acad_id: number;
  curs_acad_nom: string;
  cicle_id: number;
  cicle_codi: string;
  cicle_nom: string;
  curs: number;
  grup_id: number;
  grup_codi: string;
  tipus: string;
  estat: string;
  created_at: string;
  moduls: ModulHistRow[];
};

export type AlumneExpedient = {
  alumne: AlumneSummary;
  tutors_legals: TutorLegalRow[];
  matricules: MatriculaHistRow[];
};

export type GrupExpedient = {
  grup_id: number;
  grup_codi: string;
  curs_acad_id: number;
  curs_acad_nom: string;
  cicle_codi: string;
  cicle_nom: string;
  cicle_nivell: string;
  curs: number;
  tutor_user_id: number | null;
  tutor_nom_complet: string | null;
  alumnes: {
    alumne_id: number;
    matricula_id: number;
    nom: string;
    cognoms: string;
    dni: string | null;
    ralc: string;
    estat: string;
  }[];
};

export type SearchHit = {
  kind: "alumne" | "grup" | "cicle";
  id: number;
  label: string;
  sub: string | null;
  extra: Record<string, number>;
};

export const archiveApi = {
  alumneExpedient: (alumneId: number) =>
    api<AlumneExpedient>(`/archive/alumne/${alumneId}/expedient`),
  grupExpedient: (grupId: number) =>
    api<GrupExpedient>(`/archive/grup/${grupId}/expedient`),
  search: (q: string) =>
    api<SearchHit[]>(`/archive/search?q=${encodeURIComponent(q)}`),
};
