/** ConfirmDialog — wraps Modal with a question + Confirm/Cancel buttons. */
import { Modal } from "./Modal";

import buttonStyles from "./Button.module.css";

export type ConfirmDialogProps = {
  title: string;
  message: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "danger";
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
};

export function ConfirmDialog({
  title,
  message,
  detail,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancel·lar",
  variant = "default",
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Modal
      title={title}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button type="button" className={buttonStyles.btn} onClick={onClose}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={`${buttonStyles.btn} ${variant === "danger" ? buttonStyles.danger : buttonStyles.primary}`}
            onClick={async () => {
              await onConfirm();
              onClose();
            }}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p style={{ fontSize: 14, color: "var(--ink-2)", margin: 0, lineHeight: 1.65 }}>{message}</p>
      {detail && (
        <p
          style={{
            fontSize: 12.5,
            color: "var(--ink-3)",
            marginTop: 10,
            fontFamily: "var(--mono)",
            lineHeight: 1.5,
            padding: "10px 12px",
            background: "var(--bg-2)",
            borderRadius: "var(--r)",
            border: "1px solid var(--line)",
          }}
        >
          {detail}
        </p>
      )}
    </Modal>
  );
}
