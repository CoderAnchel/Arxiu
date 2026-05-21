/** Holds the currently selected curs acadèmic — used for filtering across pages. */
import { create } from "zustand";

import type { CursAcademic } from "@/api/catalog";

type CursAcadState = {
  current: CursAcademic | null;
  setCurrent: (c: CursAcademic | null) => void;
};

export const useCursAcadStore = create<CursAcadState>(set => ({
  current: null,
  setCurrent: c => set({ current: c }),
}));
