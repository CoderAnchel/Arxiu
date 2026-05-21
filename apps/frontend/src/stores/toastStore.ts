/** Toast queue. Components call `pushToast({ type, message })`; the
 * `<ToastContainer />` rendered once at the App root handles auto-dismissal. */
import { create } from "zustand";

export type ToastType = "success" | "warn" | "error" | "info";

export type Toast = {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
};

type ToastState = {
  toasts: Toast[];
  pushToast: (t: Omit<Toast, "id">) => string;
  dismissToast: (id: string) => void;
};

let _seq = 0;

export const useToastStore = create<ToastState>(set => ({
  toasts: [],
  pushToast: t => {
    const id = `t${++_seq}`;
    set(s => ({ toasts: [...s.toasts, { id, duration: 3000, ...t }] }));
    return id;
  },
  dismissToast: id =>
    set(s => ({
      toasts: s.toasts.filter(t => t.id !== id),
    })),
}));

export const toast = {
  success: (message: string) => useToastStore.getState().pushToast({ type: "success", message }),
  warn: (message: string) => useToastStore.getState().pushToast({ type: "warn", message }),
  error: (message: string) => useToastStore.getState().pushToast({ type: "error", message }),
  info: (message: string) => useToastStore.getState().pushToast({ type: "info", message }),
};
