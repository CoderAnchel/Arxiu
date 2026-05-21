/** Paperera — admin-only listing + restore of soft-deleted entities. */
import { api } from "./client";

export type TrashKind =
  | "alumne"
  | "cicle"
  | "modul"
  | "ra"
  | "grup"
  | "matricula"
  | "assignacio_docent";

export type TrashItem = {
  id: number;
  label: string;
  sub: string;
  deleted_at: string | null;
  deleted_by_user_id: number | null;
};

export type TrashByKind = Record<TrashKind, TrashItem[]>;

export const trashApi = {
  list: (kind?: TrashKind) => {
    const qs = kind ? `?kind=${kind}` : "";
    return api<TrashByKind>(`/trash${qs}`);
  },
  restore: (kind: TrashKind, id: number) =>
    api<void>(`/trash/${kind}/${id}/restore`, { method: "POST" }),
};
