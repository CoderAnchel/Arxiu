/** Typed client for avaluacions + qualificacions. */
import { api } from "./client";

export type EstatAvaluacio = "oberta" | "docent" | "junta" | "tancada";

export type Avaluacio = {
  id: number;
  curs_acad_id: number;
  nom: string;
  ordre: number;
  estat: EstatAvaluacio;
  data_inici: string | null;
  data_tancament: string | null;
};

export type GradeMatrixAlumne = {
  matricula_id: number;
  alumne_id: number;
  nom: string;
  cognoms: string;
  dni: string | null;
  ralc: string;
};

export type GradeMatrixRa = {
  id: number;
  ordre: number;
  codi: string;
  descripcio: string;
  pes: string;
};

export type GradeMatrixCell = {
  matricula_id: number;
  ra_id: number;
  nota: number | null;
  comentari: string | null;
};

export type GradeMatrixModulCell = {
  matricula_id: number;
  nota: number | null;
  comentari: string | null;
};

export type GradeMatrix = {
  grup_id: number;
  modul_id: number;
  avaluacio_id: number;
  avaluacio_estat: EstatAvaluacio;
  can_edit: boolean;
  alumnes: GradeMatrixAlumne[];
  ras: GradeMatrixRa[];
  cells: GradeMatrixCell[];
  modul_cells: GradeMatrixModulCell[];
};

export type QualifRaPatch = {
  matricula_id: number;
  ra_id: number;
  nota: number | null;
  comentari?: string | null;
};

export type QualifModulPatch = {
  matricula_id: number;
  nota: number | null;
  comentari?: string | null;
};

export type QualifRaPatchResult = {
  matricula_id: number;
  ra_id: number;
  ok: boolean;
  error?: string | null;
};

export type QualifModulPatchResult = {
  matricula_id: number;
  ok: boolean;
  error?: string | null;
};

export type BulkPatchResponse = {
  results: QualifRaPatchResult[];
  saved: number;
  failed: number;
};

export type BulkModulPatchResponse = {
  results: QualifModulPatchResult[];
  saved: number;
  failed: number;
};

export const gradingApi = {
  listAvaluacions: (curs_acad_id?: number) =>
    api<Avaluacio[]>(
      `/avaluacions${curs_acad_id !== undefined ? `?curs_acad_id=${curs_acad_id}` : ""}`,
    ),
  createAvaluacio: (body: {
    curs_acad_id: number;
    nom: string;
    ordre: number;
    data_inici?: string | null;
  }) => api<Avaluacio>("/avaluacions", { method: "POST", body }),
  transition: (id: number, target: EstatAvaluacio) =>
    api<Avaluacio>(`/avaluacions/${id}/transition`, {
      method: "POST",
      body: { target },
    }),

  getGradeMatrix: (params: { grup_id: number; modul_id: number; avaluacio_id: number }) => {
    const sp = new URLSearchParams({
      grup_id: String(params.grup_id),
      modul_id: String(params.modul_id),
      avaluacio_id: String(params.avaluacio_id),
    });
    return api<GradeMatrix>(`/qualificacions/ra?${sp.toString()}`);
  },

  batchPatch: (avaluacio_id: number, patches: QualifRaPatch[]) =>
    api<BulkPatchResponse>("/qualificacions/ra/batch", {
      method: "PATCH",
      body: { avaluacio_id, patches },
    }),

  batchPatchModul: (avaluacio_id: number, modul_id: number, patches: QualifModulPatch[]) =>
    api<BulkModulPatchResponse>("/qualificacions/modul/batch", {
      method: "PATCH",
      body: { avaluacio_id, modul_id, patches },
    }),
};
