import { useEffect, useMemo, useRef, useState } from "react";

import type { Command, StageId, Status } from "../../api/commands";
import {
  deleteCommand,
  listCommands,
  reorderCommands,
  updateCommand,
} from "../../api/commands";
import { isHttpError } from "../../api/http";
import { DEFAULT_STAGE_LABELS, STAGES, STATUSES } from "./constants";

import {
  getActiveSession,
  startSession,
  stopSession,
  getLatestSessionsByStageId,
} from "../../api/sessions";
import type { LatestSessionsByStageId, SessionActive } from "../../api/sessions";

import { CreateCommandModal } from "./CreateCommandModal";
import { CommandDrawer } from "./CommandDrawer";

import { getBoard, updateBoard, updateStageLabels } from "../../api/board";
import type { BoardState } from "../../api/board";
import {
  listSnapshots,
  loadSnapshot,
  patchSnapshot,
  saveSnapshot,
} from "../../api/snapshots";
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
    | { stage_id: StageId; beforeId: number | null; afterId: number | null }
    | null
  >(null);

  const [activeSession, setActiveSession] = useState<SessionActive>({ active: false });
  const [latestByStageId, setLatestByStageId] = useState<LatestSessionsByStageId>({
    DESIGN: null,
    BUILD: null,
    REVIEW: null,
    COMPLETE: null,
  });
  const [nowMs, setNowMs] = useState(() => Date.now());

  const [startMode, setStartMode] = useState(false);

  const [board, setBoard] = useState<BoardState | null>(null);
  const [boardNameDraft, setBoardNameDraft] = useState<string>("");
  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const [editingStageId, setEditingStageId] = useState<StageId | null>(null);
  const [stageLabelDraft, setStageLabelDraft] = useState<string>("");

  const [snapshots, setSnapshots] = useState<SnapshotSummary[]>([]);
  const [snapshotsOpen, setSnapshotsOpen] = useState(false);

  const [renamingSnapshotId, setRenamingSnapshotId] = useState<number | null>(null);
  const [snapshotNameDraft, setSnapshotNameDraft] = useState<string>("");
  const snapshotRenameInputRef = useRef<HTMLInputElement | null>(null);

  const [focusedStageId, setFocusedStageId] = useState<StageId>("DESIGN");
  const [createFor, setCreateFor] = useState<StageId | null>(null);
  const [selected, setSelected] = useState<Command | null>(null);

  const stageLabels = useMemo((): Record<StageId, string> => {
    const overrides = board?.stage_labels ?? null;
    return {
      ...DEFAULT_STAGE_LABELS,
      ...(overrides ?? {}),
    } as Record<StageId, string>;
  }, [board?.stage_labels]);

  const commandsByStageId = useMemo(() => {
    const map = new Map<StageId, Command[]>();
    for (const s of STAGES) map.set(s, []);
    for (const cmd of commands) {
      map.get(cmd.stage_id)?.push(cmd);
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

  function buildReorderPayload(next: Command[]): Record<StageId, number[]> {
    const by: Record<StageId, number[]> = {
      DESIGN: [],
      BUILD: [],
      REVIEW: [],
      COMPLETE: [],
    };
    for (const c of next) by[c.stage_id].push(c.id);
    return by;
  }

  async function commitReorder(next: Command[]): Promise<void> {
    // Persist ordering for all stages (simplest correctness; small dataset).
    const by_stage_id = buildReorderPayload(next);
    await reorderCommands({ by_stage_id });
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

      const latest = await getLatestSessionsByStageId();
      setLatestByStageId(latest);

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
    if (renamingSnapshotId === null) return;
    const t = window.setTimeout(() => {
      snapshotRenameInputRef.current?.focus();
      snapshotRenameInputRef.current?.select();
    }, 0);
    return () => window.clearTimeout(t);
  }, [renamingSnapshotId]);

  function pencilSvg() {
    return (
      <svg
        className={styles.icon}
        viewBox="0 0 24 24"
        aria-hidden="true"
        focusable="false"
      >
        <path
          fill="currentColor"
          d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25Zm18.71-11.04a1.003 1.003 0 0 0 0-1.42l-2.5-2.5a1.003 1.003 0 0 0-1.42 0l-1.83 1.83 3.75 3.75 1.99-1.66Z"
        />
      </svg>
    );
  }

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

  useEffect(() => {
    if (!startMode) return;

    function onKeyDown(e: KeyboardEvent): void {
      if (e.key === "Escape") setStartMode(false);
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [startMode]);

  function openCreate(stage_id: StageId): void {
    setCreateFor(stage_id);
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
    stage_id: StageId,
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
      stage_id,
      beforeId: before ? cmd.id : null,
      afterId: before ? null : cmd.id,
    });
  }

  function onColumnDragOver(e: React.DragEvent, stage_id: StageId): void {
    if (draggingId === null) return;
    // Only handle "background" drag-over events; card-level handlers set
    // precise insertion targets.
    if (e.target !== e.currentTarget) return;

    e.preventDefault();
    e.dataTransfer.dropEffect = "move";

    // If we're over the column but not a specific card, append to bottom.
    setDropTarget({ stage_id, beforeId: null, afterId: null });
  }

  async function onDrop(e: React.DragEvent): Promise<void> {
    if (draggingId === null || dropTarget === null) return;
    e.preventDefault();

    const moving = commands.find((c) => c.id === draggingId);
    if (!moving) return;

    const prev = commands;
    const without = prev.filter((c) => c.id !== draggingId);
    const targetList = without.filter((c) => c.stage_id === dropTarget.stage_id);
    const insertIndex = computeInsertIndex(
      targetList,
      dropTarget.beforeId,
      dropTarget.afterId
    );

    const moved: Command = { ...moving, stage_id: dropTarget.stage_id };
    const nextTarget = [
      ...targetList.slice(0, insertIndex),
      moved,
      ...targetList.slice(insertIndex),
    ];

    // Rebuild full list preserving other stages.
    const next: Command[] = [];
    for (const s of STAGES) {
      if (s === dropTarget.stage_id) {
        next.push(...nextTarget);
      } else {
        next.push(...without.filter((c) => c.stage_id === s));
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

  async function onStartSession(command_id: number): Promise<void> {
    setError(null);
    try {
      await startSession(command_id);
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

  function beginRenameSnapshot(s: SnapshotSummary): void {
    setRenamingSnapshotId(s.id);
    setSnapshotNameDraft(s.name);
  }

  async function commitRenameSnapshot(snapshotId: number): Promise<void> {
    const cleaned = snapshotNameDraft.trim();
    if (!cleaned) {
      // Invalid: revert.
      setRenamingSnapshotId(null);
      setSnapshotNameDraft("");
      return;
    }

    setError(null);
    try {
      const updated = await patchSnapshot(snapshotId, { name: cleaned });
      setSnapshots((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not rename snapshot";
      setError(msg);
    } finally {
      setRenamingSnapshotId(null);
      setSnapshotNameDraft("");
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

  const activeStageId: StageId | null =
    "active" in activeSession && activeSession.active === false
      ? null
      : (activeSession as Exclude<SessionActive, { active: false }>).stage_id;

  const activeCommandId: number | null =
    "active" in activeSession && activeSession.active === false
      ? null
      : (activeSession as Exclude<SessionActive, { active: false }>).command_id;

  const effectiveFocusedStageId: StageId = activeStageId ?? focusedStageId;

  const activeCommand: Command | null = useMemo(() => {
    if (activeCommandId === null) return null;
    return commands.find((c) => c.id === activeCommandId) ?? null;
  }, [activeCommandId, commands]);

  const stopDisabled = activeStageId === null;
  const startDisabled = activeStageId !== null;

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
    if (activeStageId === null) return null;
    const startIso = (activeSession as Exclude<SessionActive, { active: false }>).started_at;
    const startMs = Date.parse(startIso);
    if (Number.isNaN(startMs)) return null;
    return formatDuration((nowMs - startMs) / 1000);
  }, [activeSession, activeStageId, nowMs]);

  function startSessionLabel(): string {
    if (startDisabled) return "Start";
    return startMode ? "Cancel" : "Start";
  }

  async function onToggleStartMode(): Promise<void> {
    if (startDisabled) return;
    if (startMode) {
      setStartMode(false);
      return;
    }
    if (commands.length === 0) {
      setError("Create a task first, then Start.");
      return;
    }
    setStartMode(true);
  }

  async function onCommitStageLabel(stage_id: StageId, nextLabel: string): Promise<void> {
    const cleaned = nextLabel.trim();
    if (!cleaned) return;

    setError(null);
    try {
      const next = await updateStageLabels({
        stage_labels: {
          ...(board?.stage_labels ?? {}),
          [stage_id]: cleaned,
        },
      });
      setBoard(next);
    } catch (e) {
      const msg = isHttpError(e) ? e.message : "Could not update stage label";
      setError(msg);
    }
  }

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
              {activeStageId === null
                ? "No active session"
                : `Active: ${stageLabels[activeStageId]}${
                    activeCommand ? ` · ${activeCommand.title}` : ""
                  }`}
            </span>
            {activeStageId !== null && sessionTimerText ? (
              <span className={styles.sessionTimer}>{sessionTimerText}</span>
            ) : null}

            <button
              type="button"
              className={`${styles.tinyButton} ${
                startDisabled ? styles.disabledRed : styles.greenHover
              }`}
              disabled={startDisabled}
              title={startDisabled ? "Stop the current session before starting another" : "Start a session by selecting a task"}
              onClick={() => void onToggleStartMode()}
            >
              {startSessionLabel()}
            </button>

            <button
              type="button"
              className={`${styles.tinyButton} ${styles.stopGreenHover}`}
              title={
                activeStageId === null
                  ? "Add a task"
                  : `Add a task in ${stageLabels[effectiveFocusedStageId]}`
              }
              onClick={() => openCreate(effectiveFocusedStageId)}
            >
              Add
            </button>

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
                      <div
                        key={s.id}
                        className={styles.snapshotRow}
                        role="none"
                      >
                        {renamingSnapshotId === s.id ? (
                          <input
                            ref={snapshotRenameInputRef}
                            className={styles.snapshotRenameInput}
                            value={snapshotNameDraft}
                            aria-label="Snapshot name"
                            onChange={(e) => setSnapshotNameDraft(e.target.value)}
                            onBlur={() => void commitRenameSnapshot(s.id)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.currentTarget.blur();
                              }
                              if (e.key === "Escape") {
                                setRenamingSnapshotId(null);
                                setSnapshotNameDraft("");
                              }
                            }}
                          />
                        ) : (
                          <button
                            type="button"
                            className={styles.dropdownItem}
                            onClick={() => void onLoadSnapshot(s.id)}
                            onKeyDown={(e) => {
                              if (e.key === "F2") {
                                e.preventDefault();
                                beginRenameSnapshot(s);
                              }
                            }}
                          >
                            <span className={styles.snapshotRowText}>
                              {s.name} - {formatLocal(s.saved_at) ?? s.saved_at}
                            </span>
                          </button>
                        )}

                        {renamingSnapshotId === s.id ? null : (
                          <button
                            type="button"
                            className={styles.snapshotEditButton}
                            title="Rename (F2)"
                            aria-label="Rename snapshot"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              beginRenameSnapshot(s);
                            }}
                          >
                            {pencilSvg()}
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              ) : null}
            </div>
          </div>

          <div className={styles.helperRow}>
            {startMode ? (
              <span className={styles.helperText}>
                Select a task card to start a session. Press Esc to cancel.
              </span>
            ) : (
              <span className={styles.helperText}>
                Tip: drag the grip on a card to reorder or move it between stages.
              </span>
            )}
          </div>
        </div>
        <div className={styles.headerRight}>
          {loading ? <span className={styles.muted}>Loading…</span> : null}
          {error ? <span className={styles.error}>{error}</span> : null}
        </div>
      </div>

      <div
        className={`${styles.board} ${activeStageId ? styles.boardHasActive : ""} ${
          startMode ? styles.boardStartMode : ""
        }`}
      >
        {STAGES.map((stage_id) => (
          <div
            key={stage_id}
            className={`${styles.column} ${
              activeStageId === stage_id ? styles.columnActive : ""
            } ${
              dropTarget?.stage_id === stage_id && draggingId !== null
                ? styles.columnDropTarget
                : ""
            } ${
              effectiveFocusedStageId === stage_id ? styles.columnFocused : ""
            }`}
            onMouseDown={() => setFocusedStageId(stage_id)}
          >
            <div className={styles.columnHeader}>
              {editingStageId === stage_id ? (
                <input
                  className={styles.stageLabelInput}
                  value={stageLabelDraft}
                  aria-label="Stage label"
                  onChange={(e) => setStageLabelDraft(e.target.value)}
                  onBlur={() => {
                    setEditingStageId(null);
                    void onCommitStageLabel(stage_id, stageLabelDraft);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      (e.currentTarget as HTMLInputElement).blur();
                    }
                    if (e.key === "Escape") {
                      setEditingStageId(null);
                      setStageLabelDraft(stageLabels[stage_id]);
                    }
                  }}
                  autoFocus
                />
              ) : (
                <h2 className={styles.columnTitle}>{stageLabels[stage_id]}</h2>
              )}

              <div className={styles.columnHeaderActions}>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  title="Rename stage"
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingStageId(stage_id);
                    setStageLabelDraft(stageLabels[stage_id]);
                  }}
                >
                  Rename
                </button>
              </div>
            </div>

            {latestByStageId[stage_id] ? (
              <div className={styles.paneSessionMeta}>
                {latestByStageId[stage_id]?.started_at ? (
                  <span>
                    Started: {formatLocal(latestByStageId[stage_id]!.started_at)}
                  </span>
                ) : null}

                {latestByStageId[stage_id]?.ended_at ? (
                  <span>
                    Ended: {formatLocal(latestByStageId[stage_id]!.ended_at!)}
                  </span>
                ) : activeStageId === stage_id && sessionTimerText ? (
                  <span>Elapsed: {sessionTimerText}</span>
                ) : null}
              </div>
            ) : null}

            <div
              className={styles.cards}
              onDragOver={(e) => onColumnDragOver(e, stage_id)}
              onDrop={(e) => void onDrop(e)}
            >
              {(commandsByStageId.get(stage_id) ?? []).length === 0 ? (
                <div className={styles.empty}>No tasks yet</div>
              ) : null}

              {(commandsByStageId.get(stage_id) ?? []).map((cmd) => (
                <div
                  key={cmd.id}
                  className={`${styles.card} ${
                    draggingId === cmd.id ? styles.cardDragging : ""
                  } ${
                    activeCommandId === cmd.id ? styles.cardActiveTask : ""
                  } ${
                    dropTarget?.stage_id === stage_id && dropTarget.beforeId === cmd.id
                      ? styles.cardDropBefore
                      : ""
                  } ${
                    dropTarget?.stage_id === stage_id && dropTarget.afterId === cmd.id
                      ? styles.cardDropAfter
                      : ""
                  }`}
                  onClick={() => {
                    if (startMode && !startDisabled) {
                      setStartMode(false);
                      void onStartSession(cmd.id);
                      return;
                    }
                    setSelected(cmd);
                  }}
                  onDragOver={(e) => onCardDragOver(e, stage_id, cmd)}
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
          initialStageId={createFor}
          stageLabels={stageLabels}
          onClose={() => setCreateFor(null)}
          onCreated={refresh}
          setError={(msg) => setError(msg || null)}
        />
      ) : null}

      {selected ? (
        <CommandDrawer
          command={selected}
          stageLabels={stageLabels}
          onClose={() => setSelected(null)}
          onRefreshCommands={refresh}
          setError={(msg) => setError(msg || null)}
        />
      ) : null}
    </section>
  );
}

