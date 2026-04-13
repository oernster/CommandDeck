import { useEffect } from "react";

import styles from "./DestructiveGuardModal.module.css";

export type DestructiveGuardModalProps = {
  title: string;
  body: string;
  busy: boolean;
  onSaveAndContinue: () => void;
  onContinueWithoutSaving: () => void;
  onCancel: () => void;
};

export function DestructiveGuardModal(props: DestructiveGuardModalProps) {
  const {
    title,
    body,
    busy,
    onSaveAndContinue,
    onContinueWithoutSaving,
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
            className={styles.primary}
            disabled={busy}
            onClick={onSaveAndContinue}
          >
            Save snapshot and continue
          </button>
          <button
            type="button"
            className={styles.secondary}
            disabled={busy}
            onClick={onContinueWithoutSaving}
          >
            Continue without saving
          </button>
          <button
            type="button"
            className={styles.cancel}
            disabled={busy}
            onClick={onCancel}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

