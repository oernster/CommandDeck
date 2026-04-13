import { useEffect, useMemo, useRef, useState } from "react";

import type { Command, StageId, Status } from "../../api/commands";
import { deleteCommand, updateCommand } from "../../api/commands";
import type { Outcome } from "../../api/outcomes";
import { createOutcome, deleteOutcome, listOutcomes } from "../../api/outcomes";
import { isHttpError } from "../../api/http";
import { DEFAULT_STAGE_LABELS, STAGES, STATUSES } from "./constants";

import styles from "./CommandDrawer.module.css";

export type CommandDrawerProps = {
  command: Command;
  stageLabels: Record<StageId, string>;
  onClose: () => void;
  onRefreshCommands: () => Promise<void>;
  setError: (msg: string) => void;
};

function formatTimestamp(ts: string): string {
  // API already returns ISO-8601 Z; keep it readable.
  // Example: 2026-01-01T12:34:56Z
  return ts.replace("T", " ").replace("Z", " UTC");
}

export function CommandDrawer(props: CommandDrawerProps) {
  const { command, stageLabels, onClose, onRefreshCommands, setError } = props;

  const [title, setTitle] = useState(command.title);
  const [stage_id, setStageId] = useState<StageId>(command.stage_id);
  const [status, setStatus] = useState<Status>(command.status);

  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [loadingOutcomes, setLoadingOutcomes] = useState(true);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const noteRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    // Keep state in sync when the selected command changes.
    setTitle(command.title);
    setStageId(command.stage_id);
    setStatus(command.status);
  }, [command.id, command.title, command.stage_id, command.status]);

  async function refreshOutcomes(): Promise<void> {
    setLoadingOutcomes(true);
    try {
      const items = await listOutcomes(command.id);
      setOutcomes(items);
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Failed to load outcomes";
      setError(msg);
    } finally {
      setLoadingOutcomes(false);
    }
  }

  useEffect(() => {
    void refreshOutcomes();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command.id]);

  const dirty = useMemo(() => {
    return (
      title.trim() !== command.title ||
      stage_id !== command.stage_id ||
      status !== command.status
    );
  }, [title, stage_id, status, command.title, command.stage_id, command.status]);

  async function onSave(): Promise<void> {
    if (!dirty) return;
    setError("");
    setSaving(true);
    try {
      await updateCommand(command.id, {
        title: title.trim(),
        stage_id,
        status,
      });
      await onRefreshCommands();
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Could not save command";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(): Promise<void> {
    const ok = window.confirm("Delete this command?");
    if (!ok) return;

    setError("");
    setSaving(true);
    try {
      await deleteCommand(command.id);
      await onRefreshCommands();
      onClose();
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Could not delete command";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function onAddOutcome(): Promise<void> {
    const trimmed = note.trim();
    if (!trimmed) return;

    setError("");
    setSaving(true);
    try {
      await createOutcome(command.id, { note: trimmed });
      setNote("");
      await refreshOutcomes();
      noteRef.current?.focus();
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Could not save outcome";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteOutcome(outcomeId: number): Promise<void> {
    const ok = window.confirm("Delete this outcome?");
    if (!ok) return;

    setError("");
    setSaving(true);
    try {
      await deleteOutcome(outcomeId);
      await refreshOutcomes();
    } catch (err) {
      const msg = isHttpError(err) ? err.message : "Could not delete outcome";
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
      aria-label="Command details"
      onMouseDown={onBackdropMouseDown}
      onKeyDown={onKeyDown}
      tabIndex={-1}
    >
      <aside className={styles.drawer}>
        <div className={styles.header}>
          <div>
            <h3 className={styles.title}>Command</h3>
            <div className={styles.meta}>Created: {formatTimestamp(command.created_at)}</div>
          </div>
          <button type="button" className={styles.close} onClick={onClose}>
            Close
          </button>
        </div>

        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>Details</h4>

          <div className={styles.row}>
            <span className={styles.label}>Title</span>
            <input
              className={styles.input}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
            />
          </div>

          <div className={styles.row}>
            <span className={styles.label}>Stage</span>
            <select
              className={styles.select}
              value={stage_id}
              onChange={(e) => setStageId(e.target.value as StageId)}
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {stageLabels[s] ?? DEFAULT_STAGE_LABELS[s]}
                </option>
              ))}
            </select>
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

          <div className={styles.actions}>
            <button type="button" className={styles.danger} onClick={() => void onDelete()}>
              Delete
            </button>

            <button
              type="button"
              className={styles.primary}
              disabled={!dirty || saving || title.trim().length === 0}
              onClick={() => void onSave()}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>

        <div className={styles.section}>
          <h4 className={styles.sectionTitle}>Outcomes</h4>

          <div className={styles.outcomes}>
            {loadingOutcomes ? <div className={styles.empty}>Loading…</div> : null}
            {!loadingOutcomes && outcomes.length === 0 ? (
              <div className={styles.empty}>No outcomes recorded</div>
            ) : null}

            {outcomes.map((o) => (
              <div key={o.id} className={styles.outcome}>
                <div className={styles.outcomeNote}>{o.note}</div>
                <div className={styles.outcomeMeta}>
                  <div>{formatTimestamp(o.created_at)}</div>
                  <button
                    type="button"
                    className={styles.secondary}
                    onClick={() => void onDeleteOutcome(o.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className={styles.row}>
            <span className={styles.label}>New</span>
            <textarea
              ref={noteRef}
              className={styles.textarea}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Record what happened…"
            />
          </div>

          <div className={styles.actions}>
            <span />
            <button
              type="button"
              className={styles.primary}
              disabled={saving || note.trim().length === 0}
              onClick={() => void onAddOutcome()}
            >
              {saving ? "Saving…" : "Add outcome"}
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

