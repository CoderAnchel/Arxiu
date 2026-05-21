/** Generic modal — overlay + card + escape-to-close + outside-click-to-close. */
import { useEffect, type ReactNode } from "react";

import styles from "./Modal.module.css";

export type ModalProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  maxWidth?: number;
  closeOnBackdrop?: boolean;
};

export function Modal({
  title,
  subtitle,
  children,
  footer,
  onClose,
  maxWidth = 620,
  closeOnBackdrop = true,
}: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className={styles.overlay}
      onClick={() => closeOnBackdrop && onClose()}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="arxiu-modal-title"
        className={styles.box}
        style={{ maxWidth }}
        onClick={e => e.stopPropagation()}
      >
        <header className={styles.head}>
          <div className={styles.headBody}>
            <h2 id="arxiu-modal-title" className={styles.title}>
              {title}
            </h2>
            {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
          </div>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            aria-label="Tancar"
          >
            ×
          </button>
        </header>
        <div className={styles.body}>{children}</div>
        {footer && <footer className={styles.foot}>{footer}</footer>}
      </div>
    </div>
  );
}
