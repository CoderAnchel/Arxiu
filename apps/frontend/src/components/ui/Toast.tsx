/** Toast container — fixed bottom-right stack. Auto-dismiss with progress bar. */
import { useEffect } from "react";

import { type Toast as ToastModel, useToastStore } from "@/stores/toastStore";

import styles from "./Toast.module.css";

const TYPE_LABEL: Record<ToastModel["type"], string> = {
  success: "✓",
  warn: "!",
  error: "×",
  info: "i",
};

function ToastItem({ toast }: { toast: ToastModel }) {
  const dismiss = useToastStore(s => s.dismissToast);
  useEffect(() => {
    const t = setTimeout(() => dismiss(toast.id), toast.duration ?? 3000);
    return () => clearTimeout(t);
  }, [toast.id, toast.duration, dismiss]);

  return (
    <div role="status" className={`${styles.toast} ${styles[toast.type]}`}>
      <span className={styles.ico}>{TYPE_LABEL[toast.type]}</span>
      <span className={styles.msg}>{toast.message}</span>
      <span className={styles.bar} style={{ animationDuration: `${toast.duration ?? 3000}ms` }} />
    </div>
  );
}

export function ToastContainer() {
  const toasts = useToastStore(s => s.toasts);
  return (
    <div className={styles.container} aria-live="polite">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
