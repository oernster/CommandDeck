import { useEffect, useMemo, useState } from "react";

import type { Category, Command, Status } from "../../api/commands";
import {
  deleteCommand,
  listCommands,
  updateCommand,
} from "../../api/commands";
import { isHttpError } from "../../api/http";
import { CATEGORIES, STATUSES } from "./constants";

import { getActiveSession, startSession, stopSession } from "../../api/sessions";
import type { SessionActive } from "../../api/sessions";

import { CreateCommandModal } from "./CreateCommandModal";
import { CommandDrawer } from "./CommandDrawer";

import styles from "./Board.module.css";

function statusClass(status: Status): string {
  switch (status) {
    case "Not Started":
      return styles.statusNotStarted;
    case "In Progress":
      return styles.statusInProgress;
    case "Blocked":
      return styles.statusBlocked;
    case "Complete":
      return styles.statusComplete;
  }
}

export function Board() {
  const [commands, setCommands] = useState<Command[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeSession, setActiveSession] = useState<SessionActive>({ active: false });
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [createFor, setCreateFor] = useState<Category | null>(null);
  const [selected, setSelected] = useState<Command | null>(null);

  const commandsByCategory = useMemo(() => {
    const map = new Map<Category, Command[]>();
    for (const c of CATEGORIES) map.set(c, []);
    for (const cmd of commands) {
      map.get(cmd.category)?.push(cmd);
    }
    return map;
  }, [commands]);

  async function refresh(): Promise<void> {
    setError(null);
    setLoading(true);
    try {
      const items = await listCommands();
      setCommands(items);

      const s = await getActiveSession();
      setActiveSession(s);
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Failed to load commands";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  useEffect(() => {
    const t = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  function openCreate(category: Category): void {
    setCreateFor(category);
  }

  async function onChangeStatus(id: number, status: Status): Promise<void> {
    setError(null);
    try {
      await updateCommand(id, { status });
      await refresh();
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not update command";
      setError(msg);
    }
  }

  async function onDelete(id: number): Promise<void> {
    const ok = window.confirm("Delete this command?");
    if (!ok) return;

    setError(null);
    try {
      await deleteCommand(id);
      await refresh();
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not delete command";
      setError(msg);
    }
  }

  async function onStartSession(category: Category): Promise<void> {
    setError(null);
    try {
      await startSession(category);
      await refresh();
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Session could not be started";
      setError(msg);
    }
  }

  async function onStopSession(): Promise<void> {
    setError(null);
    try {
      await stopSession();
      await refresh();
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Session could not be stopped";
      setError(msg);
    }
  }

  const activeCategory: Category | null =
    "active" in activeSession && activeSession.active === false
      ? null
      : (activeSession as Exclude<SessionActive, { active: false }>).category;

  function formatDuration(seconds: number): string {
    const s = Math.max(0, Math.floor(seconds));
    const hh = Math.floor(s / 3600)
      .toString()
      .padStart(2, "0");
    const mm = Math.floor((s % 3600) / 60)
      .toString()
      .padStart(2, "0");
    const ss = Math.floor(s % 60)
      .toString()
      .padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  }

  const sessionTimerText = useMemo(() => {
    if (activeCategory === null) return null;
    const startIso = (activeSession as Exclude<SessionActive, { active: false }>).started_at;
    const startMs = Date.parse(startIso);
    if (Number.isNaN(startMs)) return null;
    return formatDuration((nowMs - startMs) / 1000);
  }, [activeSession, activeCategory, nowMs]);

  return (
    <section className={styles.root}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Command Deck</h1>
          <div className={styles.sessionRow}>
            <span className={styles.sessionBadge}>
              {activeCategory === null ? "No active session" : `Active: ${activeCategory}`}
            </span>
            {activeCategory !== null && sessionTimerText ? (
              <span className={styles.sessionTimer}>{sessionTimerText}</span>
            ) : null}
            {activeCategory !== null ? (
              <button
                type="button"
                className={styles.tinyButton}
                onClick={() => void onStopSession()}
              >
                Stop
              </button>
            ) : null}
          </div>
        </div>
        <div className={styles.headerRight}>
          {loading ? <span className={styles.muted}>Loading…</span> : null}
          {error ? <span className={styles.error}>{error}</span> : null}
        </div>
      </div>

      <div className={styles.board}>
        {CATEGORIES.map((category) => (
          <div
            key={category}
            className={`${styles.column} ${
              activeCategory === category ? styles.columnActive : ""
            }`}
          >
            <div className={styles.columnHeader}>
              <h2 className={styles.columnTitle}>{category}</h2>
              <div className={styles.columnHeaderActions}>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => void onStartSession(category)}
                >
                  Start
                </button>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => openCreate(category)}
                >
                  Add
                </button>
              </div>
            </div>

            <div className={styles.cards}>
              {(commandsByCategory.get(category) ?? []).length === 0 ? (
                <div className={styles.empty}>No commands yet</div>
              ) : null}

              {(commandsByCategory.get(category) ?? []).map((cmd) => (
                <div
                  key={cmd.id}
                  className={styles.card}
                  onClick={() => setSelected(cmd)}
                >
                  <div className={styles.cardTop}>
                    <div className={styles.cardTitleRow}>
                      <span className={styles.cardTitle}>{cmd.title}</span>
                      <span
                        className={`${styles.statusDot} ${statusClass(cmd.status)}`}
                        aria-label={`Status: ${cmd.status}`}
                        title={cmd.status}
                      />
                    </div>

                    <div className={styles.cardActions}>
                      <label className={styles.statusLabel}>
                        <span className={styles.visuallyHidden}>Status</span>
                        <select
                          className={styles.statusSelect}
                          value={cmd.status}
                          onChange={(e) =>
                            void onChangeStatus(cmd.id, e.target.value as Status)
                          }
                          onClick={(e) => e.stopPropagation()}
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </label>

                      <button
                        type="button"
                        className={styles.dangerButton}
                        onClick={() => void onDelete(cmd.id)}
                        onMouseDown={(e) => e.stopPropagation()}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {createFor ? (
        <CreateCommandModal
          initialCategory={createFor}
          onClose={() => setCreateFor(null)}
          onCreated={refresh}
          setError={(msg) => setError(msg || null)}
        />
      ) : null}

      {selected ? (
        <CommandDrawer
          command={selected}
          onClose={() => setSelected(null)}
          onRefreshCommands={refresh}
          setError={(msg) => setError(msg || null)}
        />
      ) : null}
    </section>
  );
}

