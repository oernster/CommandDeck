import { useEffect, useMemo, useRef, useState } from "react";

import type { Category, Command, Status } from "../../api/commands";
import {
  deleteCommand,
  listCommands,
  reorderCommands,
  updateCommand,
} from "../../api/commands";
import { isHttpError } from "../../api/http";
import { CATEGORIES, STATUSES } from "./constants";

import {
  getActiveSession,
  getLatestSessionsByCategory,
  startSession,
  stopSession,
} from "../../api/sessions";
import type { LatestSessionsByCategory, SessionActive } from "../../api/sessions";

import { CreateCommandModal } from "./CreateCommandModal";
import { CommandDrawer } from "./CommandDrawer";

import { getBoard, updateBoard } from "../../api/board";
import type { BoardState } from "../../api/board";
import { listSnapshots, loadSnapshot, saveSnapshot } from "../../api/snapshots";
import type { SnapshotSummary } from "../../api/snapshots";

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

  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<
    | { category: Category; beforeId: number | null; afterId: number | null }
    | null
  >(null);

  const [activeSession, setActiveSession] = useState<SessionActive>({ active: false });
  const [latestByCategory, setLatestByCategory] = useState<LatestSessionsByCategory>({
    Design: null,
    Build: null,
    Review: null,
    Maintain: null,
    Recover: null,
  });
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [board, setBoard] = useState<BoardState | null>(null);
  const [boardNameDraft, setBoardNameDraft] = useState<string>("");
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [snapshotsOpen, setSnapshotsOpen] = useState(false);

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

  function computeInsertIndex(
    list: Command[],
    beforeId: number | null,
    afterId: number | null
  ): number {
    if (beforeId !== null) {
      const i = list.findIndex((c) => c.id === beforeId);
      return i >= 0 ? i : list.length;
    }
    if (afterId !== null) {
      const i = list.findIndex((c) => c.id === afterId);
      return i >= 0 ? i + 1 : list.length;
    }
    return list.length;
  }

  function buildReorderPayload(next: Command[]): Record<Category, number[]> {
    const by: Record<Category, number[]> = {
      Design: [],
      Build: [],
      Review: [],
      Maintain: [],
      Recover: [],
    };
    for (const c of next) by[c.category].push(c.id);
    return by;
  }

  async function commitReorder(next: Command[]): Promise<void> {
    // Persist ordering for all categories (simplest correctness; small dataset).
    const by_category = buildReorderPayload(next);
    await reorderCommands({ by_category });
  }

  async function refresh(): Promise<void> {
    setError(null);
    setLoading(true);
    try {
      const b = await getBoard();
      setBoard(b);
      setBoardNameDraft(b.name);

      const items = await listCommands();
      setCommands(items);

      const s = await getActiveSession();
      setActiveSession(s);

      const latest = await getLatestSessionsByCategory();
      setLatestByCategory(latest);

      const snaps = await listSnapshots();
      setSnapshots(snaps);
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
    if (!board?.is_new_unnamed) return;
    // Autofocus only once per mount.
    const t = window.setTimeout(() => {
      nameInputRef.current?.focus();
      nameInputRef.current?.select();
    }, 0);
    return () => window.clearTimeout(t);
  }, [board?.is_new_unnamed]);

  useEffect(() => {
    function onDocMouseDown(e: MouseEvent): void {
      const target = e.target as HTMLElement | null;
      if (!target) return;
      if (target.closest(`.${styles.snapshotsMenu}`)) return;
      setSnapshotsOpen(false);
    }

    if (!snapshotsOpen) return;
    document.addEventListener("mousedown", onDocMouseDown);
    return () => document.removeEventListener("mousedown", onDocMouseDown);
  }, [snapshotsOpen]);

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

  function gripSvg() {
    // Minimal grip icon (6 dots) - no external deps.
    return (
      <svg
        className={styles.gripIcon}
        viewBox="0 0 16 16"
        aria-hidden="true"
        focusable="false"
      >
        <circle cx="5" cy="4" r="1.2" />
        <circle cx="11" cy="4" r="1.2" />
        <circle cx="5" cy="8" r="1.2" />
        <circle cx="11" cy="8" r="1.2" />
        <circle cx="5" cy="12" r="1.2" />
        <circle cx="11" cy="12" r="1.2" />
      </svg>
    );
  }

  function onGripDragStart(e: React.DragEvent, cmd: Command): void {
    e.stopPropagation();
    setDraggingId(cmd.id);
    setDropTarget(null);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(cmd.id));
  }

  function onGripDragEnd(): void {
    setDraggingId(null);
    setDropTarget(null);
  }

  function onCardDragOver(
    e: React.DragEvent,
    category: Category,
    cmd: Command
  ): void {
    if (draggingId === null) return;
    // Don't show an insertion marker on top of the item being dragged.
    if (cmd.id === draggingId) {
      setDropTarget(null);
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = "move";

    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const before = e.clientY < rect.top + rect.height / 2;
    setDropTarget({
      category,
      beforeId: before ? cmd.id : null,
      afterId: before ? null : cmd.id,
    });
  }

  function onColumnDragOver(e: React.DragEvent, category: Category): void {
    if (draggingId === null) return;
    // Only handle "background" drag-over events; card-level handlers set
    // precise insertion targets.
    if (e.target !== e.currentTarget) return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    // If we're over the column but not a specific card, append to bottom.
    setDropTarget({ category, beforeId: null, afterId: null });
  }

  async function onDrop(e: React.DragEvent): Promise<void> {
    if (draggingId === null || dropTarget === null) return;
    e.preventDefault();

    const moving = commands.find((c) => c.id === draggingId);
    if (!moving) return;

    const prev = commands;
    const without = prev.filter((c) => c.id !== draggingId);
    const targetList = without.filter((c) => c.category === dropTarget.category);
    const insertIndex = computeInsertIndex(
      targetList,
      dropTarget.beforeId,
      dropTarget.afterId
    );

    const moved: Command = { ...moving, category: dropTarget.category };
    const nextTarget = [
      ...targetList.slice(0, insertIndex),
      moved,
      ...targetList.slice(insertIndex),
    ];

    // Rebuild full list preserving other categories.
    const next: Command[] = [];
    for (const cat of CATEGORIES) {
      if (cat === dropTarget.category) {
        next.push(...nextTarget);
      } else {
        next.push(...without.filter((c) => c.category === cat));
      }
    }

    // Optimistic UI.
    setCommands(next);
    setDraggingId(null);
    setDropTarget(null);

    try {
      await commitReorder(next);
      await refresh();
    } catch (err) {
      setCommands(prev);
      const msg = isHttpError(err) ? err.message : "Could not reorder commands";
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

  async function onSaveSnapshot(): Promise<void> {
    setError(null);
    try {
      await saveSnapshot();
      const snaps = await listSnapshots();
      setSnapshots(snaps);
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not save snapshot";
      setError(msg);
    }
  }

  async function onLoadSnapshot(snapshotId: number): Promise<void> {
    const ok = window.confirm(
      "Load this snapshot? This will overwrite commands and sessions and clear outcomes/history."
    );
    if (!ok) return;

    setError(null);
    setSnapshotsOpen(false);
    try {
      await loadSnapshot(snapshotId);
      await refresh();
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not load snapshot";
      setError(msg);
    }
  }

  async function onCommitBoardName(): Promise<void> {
    if (boardNameDraft === (board?.name ?? "")) return;
    setError(null);
    try {
      const next = await updateBoard({ name: boardNameDraft });
      setBoard(next);
      setBoardNameDraft(next.name);
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not update board name";
      setError(msg);
    }
  }

  function diskSvg() {
    return (
      <svg
        className={styles.icon}
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path
          fill="currentColor"
          d="M17 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-4-4Zm-5 16a3 3 0 1 1 0-6 3 3 0 0 1 0 6ZM6 7V5h10v2H6Z"
        />
      </svg>
    );
  }

  const activeCategory: Category | null =
    "active" in activeSession && activeSession.active === false
      ? null
      : (activeSession as Exclude<SessionActive, { active: false }>).category;

  const stopDisabled = activeCategory === null;

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

  function formatLocal(iso: string): string | null {
    const ms = Date.parse(iso);
    if (Number.isNaN(ms)) return null;

    // Example: 12 Apr 2026 05:33 (local time)
    const date = new Date(ms);
    const datePart = new Intl.DateTimeFormat(undefined, {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(date);
    const timePart = new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date);
    return `${datePart} ${timePart}`;
  }

  return (
    <section className={styles.root}>
      <div className={styles.headerRow}>
        <div className={styles.headerLeft}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>Command Deck</h1>
            <input
              ref={nameInputRef}
              className={`${styles.boardName} ${
                board?.is_new_unnamed ? styles.boardNameCue : ""
              }`}
              value={boardNameDraft}
              aria-label="Board name"
              onChange={(e) => setBoardNameDraft(e.target.value)}
              onBlur={() => void onCommitBoardName()}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.currentTarget.blur();
                }
              }}
            />
          </div>
          <div className={styles.sessionRow}>
            <span className={styles.sessionBadge}>
              {activeCategory === null ? "No active session" : `Active: ${activeCategory}`}
            </span>
            {activeCategory !== null && sessionTimerText ? (
              <span className={styles.sessionTimer}>{sessionTimerText}</span>
            ) : null}
            <button
              type="button"
              className={`${styles.tinyButton} ${
                stopDisabled ? styles.disabledRed : styles.stopGreenHover
              }`}
              disabled={stopDisabled}
              title={stopDisabled ? "No active session to stop" : "Stop active session"}
              onClick={() => void onStopSession()}
            >
              Stop
            </button>

            <button
              type="button"
              className={`${styles.globalButton} ${styles.greenHover}`}
              title="Save snapshot"
              onClick={() => void onSaveSnapshot()}
            >
              {diskSvg()}
              <span>Save</span>
            </button>

            <div className={styles.snapshotsMenu}>
              <button
                type="button"
                className={`${styles.globalButton} ${styles.greenHover}`}
                onClick={() => setSnapshotsOpen((v) => !v)}
              >
                <span>Snapshots</span>
              </button>
              {snapshotsOpen ? (
                <div className={styles.dropdown} role="menu" aria-label="Snapshots">
                  {snapshots.length === 0 ? (
                    <div className={styles.dropdownEmpty}>No snapshots yet</div>
                  ) : (
                    snapshots.map((s) => (
                      <button
                        key={s.id}
                        type="button"
                        className={styles.dropdownItem}
                        onClick={() => void onLoadSnapshot(s.id)}
                      >
                        {s.name} - {formatLocal(s.saved_at) ?? s.saved_at}
                      </button>
                    ))
                  )}
                </div>
              ) : null}
            </div>
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
                {(() => {
                  const startDisabled = activeCategory === category;
                  const startTitle = startDisabled
                    ? "This category already has an active timer"
                    : "Start a session timer for this category";

                  return (
                    <button
                      type="button"
                      className={`${styles.secondaryButton} ${
                        startDisabled ? styles.disabledRed : ""
                      }`}
                      disabled={startDisabled}
                      title={startTitle}
                      onClick={() => void onStartSession(category)}
                    >
                      Start
                    </button>
                  );
                })()}
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => openCreate(category)}
                >
                  Add
                </button>
              </div>
            </div>

            {latestByCategory[category] ? (
              <div className={styles.paneSessionMeta}>
                {latestByCategory[category]?.started_at ? (
                  <span>
                    Started: {formatLocal(latestByCategory[category]!.started_at)}
                  </span>
                ) : null}

                {latestByCategory[category]?.ended_at ? (
                  <span>
                    Ended: {formatLocal(latestByCategory[category]!.ended_at!)}
                  </span>
                ) : activeCategory === category && sessionTimerText ? (
                  <span>Elapsed: {sessionTimerText}</span>
                ) : null}
              </div>
            ) : null}

            <div
              className={styles.cards}
              onDragOver={(e) => onColumnDragOver(e, category)}
              onDrop={(e) => void onDrop(e)}
            >
              {(commandsByCategory.get(category) ?? []).length === 0 ? (
                <div className={styles.empty}>No commands yet</div>
              ) : null}

              {(commandsByCategory.get(category) ?? []).map((cmd) => (
                <div
                  key={cmd.id}
                  className={`${styles.card} ${
                    draggingId === cmd.id ? styles.cardDragging : ""
                  } ${
                    dropTarget?.category === category && dropTarget.beforeId === cmd.id
                      ? styles.cardDropBefore
                      : ""
                  } ${
                    dropTarget?.category === category && dropTarget.afterId === cmd.id
                      ? styles.cardDropAfter
                      : ""
                  }`}
                  onClick={() => setSelected(cmd)}
                  onDragOver={(e) => onCardDragOver(e, category, cmd)}
                  onDrop={(e) => {
                    e.stopPropagation();
                    void onDrop(e);
                  }}
                >
                  <div className={styles.cardTop}>
                    <div className={styles.cardTitleRow}>
                      <span className={styles.cardTitle}>{cmd.title}</span>
                      <button
                        type="button"
                        className={styles.dragHandle}
                        draggable
                        aria-label="Reorder"
                        title="Drag to reorder"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => e.stopPropagation()}
                        onDragStart={(e) => onGripDragStart(e, cmd)}
                        onDragEnd={onGripDragEnd}
                      >
                        {gripSvg()}
                      </button>
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

