import { useEffect, useMemo, useRef, useState } from "react";

import type { Category, Status } from "../../api/commands";
import { createCommand } from "../../api/commands";
import { isHttpError } from "../../api/http";
import { STATUSES } from "./constants";

import styles from "./CreateCommandModal.module.css";

export type CreateCommandModalProps = {
  initialCategory: Category;
  onClose: () => void;
  onCreated: () => Promise<void>;
  setError: (msg: string) => void;
};

export function CreateCommandModal(props: CreateCommandModalProps) {
  const { initialCategory, onClose, onCreated, setError } = props;

  const [title, setTitle] = useState("");
  const [category] = useState<Category>(initialCategory);
  const [status, setStatus] = useState<Status>("Not Started");
  const [saving, setSaving] = useState(false);
  const titleRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    titleRef.current?.focus();
  }, []);

  const canSubmit = useMemo(() => title.trim().length > 0 && !saving, [title, saving]);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (!canSubmit) return;

    setError("");
    setSaving(true);
    try {
      await createCommand({ title: title.trim(), category, status });
      await onCreated();
      onClose();
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Could not create command";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  function onBackdropMouseDown(e: React.MouseEvent<HTMLDivElement>): void {
    if (e.target === e.currentTarget) onClose();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>): void {
    if (e.key === "Escape") onClose();
  }

  return (
    <div
      className={styles.backdrop}
      role="dialog"
      aria-modal="true"
      aria-label="Create command"
      onMouseDown={onBackdropMouseDown}
      onKeyDown={onKeyDown}
      tabIndex={-1}
    >
      <form className={styles.modal} onSubmit={(e) => void onSubmit(e)}>
        <div className={styles.header}>
          <h3 className={styles.title}>Create Command</h3>
          <button type="button" className={styles.close} onClick={onClose}>
            Close
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.row}>
            <span className={styles.label}>Title</span>
            <input
              ref={titleRef}
              className={styles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="What needs doing?"
              maxLength={200}
              />
          </div>

          <div className={styles.row}>
            <span className={styles.label}>Status</span>
            <select
              className={styles.select}
              value={status}
              onChange={(e) => setStatus(e.target.value as Status)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className={styles.footer}>
          <button className={styles.primary} type="submit" disabled={!canSubmit}>
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}

