/** UI store — theme, density, sidebar state. Persisted to localStorage. */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "clar" | "fosc" | "editorial";
export type Density = "dens" | "normal" | "comode";

type UIState = {
  theme: Theme;
  density: Density;
  sidebarCollapsed: boolean;
  setTheme: (t: Theme) => void;
  setDensity: (d: Density) => void;
  toggleSidebar: () => void;
};

export const useUIStore = create<UIState>()(
  persist(
    set => ({
      theme: "clar",
      density: "normal",
      sidebarCollapsed: false,
      setTheme: t => {
        document.documentElement.setAttribute("data-theme", t);
        set({ theme: t });
      },
      setDensity: d => {
        document.documentElement.setAttribute("data-density", d);
        set({ density: d });
      },
      toggleSidebar: () => set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),
    }),
    {
      name: "arxiu-ui",
      onRehydrateStorage: () => state => {
        if (state) {
          document.documentElement.setAttribute("data-theme", state.theme);
          document.documentElement.setAttribute("data-density", state.density);
        }
      },
    },
  ),
);
