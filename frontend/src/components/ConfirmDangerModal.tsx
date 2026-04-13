import { useEffect } from "react";

// Reuse the exact styling from DestructiveGuardModal to match the reset modal.
import styles from "./DestructiveGuardModal.module.css";

export type ConfirmDangerModalProps = {
  title: string;
  body: string;
  busy: boolean;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDangerModal(props: ConfirmDangerModalProps) {
  const {
    title,
    body,
    busy,
    confirmLabel = "Yes",
    cancelLabel = "No",
    onConfirm,
    onCancel,
  } = props;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") onCancel();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  function onBackdropMouseDown(e: React.MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) onCancel();
  }

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={onBackdropMouseDown}
      tabIndex={-1}
    >
      <div className={styles.modal}>
        <div className={styles.header}>
          <h3 className={styles.title}>{title}</h3>
        </div>

        <div className={styles.body}>
          <p className={styles.bodyText}>{body}</p>
        </div>

        <div className={styles.footer}>
          <button
            type="button"
            className={styles.cancel}
            disabled={busy}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
          <button
            type="button"
            className={styles.secondary}
            disabled={busy}
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

