from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

from app.core.config import SETTINGS


def _table_has_column(conn: sqlite3.Connection, *, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == column for r in rows)


def _table_exists(conn: sqlite3.Connection, *, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_commands_stage_id(conn: sqlite3.Connection) -> None:
    """Ensure the v2 `commands.stage_id` column exists and is backfilled.

    v1 stored the workflow column as `commands.category` with human labels.
    v2 stores `stage_id` as stable IDs (DESIGN/BUILD/REVIEW/COMPLETE).

    We keep the upgrade path small and idempotent:
    - If `stage_id` is missing, add it (nullable) and backfill from `category`.
    - Legacy values Maintain/Recover are mapped to COMPLETE.
    - Any remaining null/empty values are set to DESIGN.
    """

    created_stage_id_column = False
    if not _table_has_column(conn, table="commands", column="stage_id"):
        conn.execute("ALTER TABLE commands ADD COLUMN stage_id TEXT")
        created_stage_id_column = True

    if _table_has_column(conn, table="commands", column="category"):
        # Backfill stable IDs from legacy display labels.
        conn.execute(
            "UPDATE commands SET stage_id = category WHERE stage_id IS NULL OR stage_id = ''"
        )

    # Normalize to stable IDs.
    conn.execute("UPDATE commands SET stage_id = 'DESIGN' WHERE stage_id = 'Design'")
    conn.execute("UPDATE commands SET stage_id = 'BUILD' WHERE stage_id = 'Build'")
    conn.execute("UPDATE commands SET stage_id = 'REVIEW' WHERE stage_id = 'Review'")
    conn.execute("UPDATE commands SET stage_id = 'COMPLETE' WHERE stage_id = 'Complete'")
    conn.execute(
        "UPDATE commands SET stage_id = 'COMPLETE' WHERE stage_id IN ('Maintain','Recover')"
    )

    # Final fallback to keep API validation deterministic.
    conn.execute(
        "UPDATE commands SET stage_id = 'DESIGN' WHERE stage_id IS NULL OR stage_id = ''"
    )
    conn.commit()

    # Deterministic no-op branch for coverage: when upgrading from a v2 schema
    # this function does not create the column.
    if created_stage_id_column is False:
        return


def _ensure_commands_sort_index(conn: sqlite3.Connection) -> None:
    """Ensure the `commands.sort_index` column exists and is initialized.

    The project intentionally has no migrations framework in v1. We therefore do a
    small, safe, idempotent schema upgrade at startup.

    Behavior:
    - If the column is missing, it's added with DEFAULT 0.
    - Any commands with sort_index==0 are backfilled per-category preserving the
      *current* visual order (created_at DESC, id DESC).
    - If a category is partially initialized (some rows already non-zero), any
      remaining zeros are appended after the current max sort_index.
    """

    if not _table_has_column(conn, table="commands", column="sort_index"):
        # Existing rows will receive DEFAULT 0.
        conn.execute(
            "ALTER TABLE commands ADD COLUMN sort_index INTEGER NOT NULL DEFAULT 0"
        )

    # Index helps list/reorder operations.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_commands_stage_sort "
        "ON commands(stage_id, sort_index, id)"
    )

    # Backfill only when needed; keep any existing non-zero ordering.
    stages = [
        str(r[0])
        for r in conn.execute("SELECT DISTINCT stage_id FROM commands").fetchall()
    ]
    for stage_id in stages:
        stats = conn.execute(
            (
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN sort_index = 0 THEN 1 ELSE 0 END) AS zeros "
                "FROM commands WHERE stage_id = ?"
            ),
            (stage_id,),
        ).fetchone()
        total = int(stats[0])
        zeros = int(stats[1] or 0)
        if total == 0 or zeros == 0:
            continue

        start = int(
            conn.execute(
                "SELECT COALESCE(MAX(sort_index), 0) FROM commands WHERE stage_id = ?",
                (stage_id,),
            ).fetchone()[0]
        )
        # If everything is 0, `start` will be 0 and we'll preserve the current
        # visual ordering.
        next_index = start + 1

        rows = conn.execute(
            "SELECT id FROM commands "
            "WHERE stage_id = ? AND sort_index = 0 "
            "ORDER BY created_at DESC, id DESC",
            (stage_id,),
        ).fetchall()
        for r in rows:
            conn.execute(
                "UPDATE commands SET sort_index = ? WHERE id = ?",
                (next_index, int(r[0])),
            )
            next_index += 1

    conn.commit()


def _ensure_board_state(conn: sqlite3.Connection) -> None:
    """Ensure the singleton `board_state` table exists and is initialized.

    v1.1.0 introduces a board name field. The board remains "live" (no new-board
    workflow), but we persist the user's chosen name.

    Schema rules:
    - Single row only (id=1)
    - `name` can be NULL (treated as "Untitled board" in the UI)
    - `user_named` indicates whether the user explicitly set a name
    - `created_at` is used to infer first-run behavior for autofocus/cue
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS board_state (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          name TEXT,
          user_named INTEGER NOT NULL DEFAULT 0,
          stage_labels_json TEXT,
          created_at INTEGER NOT NULL
        );
        """.strip()
    )

    # v2: stage label overrides are persisted per board.
    if not _table_has_column(conn, table="board_state", column="stage_labels_json"):
        conn.execute("ALTER TABLE board_state ADD COLUMN stage_labels_json TEXT")

    # Initialize singleton row if missing.
    row = conn.execute("SELECT id FROM board_state WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO board_state (id, name, user_named, stage_labels_json, created_at) "
            "VALUES (1, NULL, 0, NULL, strftime('%s','now'))"
        )
        conn.commit()


def _ensure_sessions_v2(conn: sqlite3.Connection) -> None:
    """Ensure the v2 `sessions` schema exists.

    v1 sessions were category-level and cannot be truthfully migrated to the new
    task-bound session model (command_id required). If an old schema is present,
    we preserve it by renaming to `sessions_legacy` and start a fresh v2 table.
    """

    if not _table_exists(conn, table="sessions"):
        conn.execute(
            """
            CREATE TABLE sessions (
              id INTEGER PRIMARY KEY,
              command_id INTEGER NOT NULL,
              stage_id TEXT NOT NULL,
              started_at INTEGER NOT NULL,
              ended_at INTEGER,
              FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE
            );
            """.strip()
        )
        conn.commit()
    else:
        # If the existing sessions table lacks required v2 columns, preserve it
        # and create a fresh v2 table.
        has_command_id = _table_has_column(conn, table="sessions", column="command_id")
        has_stage_id = _table_has_column(conn, table="sessions", column="stage_id")
        if not has_command_id or not has_stage_id:
            # Preserve any legacy/partial sessions table rather than trying to
            # mutate it in-place.
            legacy_name = "sessions_legacy"
            if _table_exists(conn, table=legacy_name):
                # A previous upgrade attempt may already have created
                # `sessions_legacy`. Ensure we still preserve the current table
                # without clobbering anything.
                i = 2
                while _table_exists(conn, table=f"{legacy_name}_{i}"):
                    i += 1
                legacy_name = f"{legacy_name}_{i}"

            conn.execute(f"ALTER TABLE sessions RENAME TO {legacy_name}")
            conn.commit()

            # Create the new v2 table.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                  id INTEGER PRIMARY KEY,
                  command_id INTEGER NOT NULL,
                  stage_id TEXT NOT NULL,
                  started_at INTEGER NOT NULL,
                  ended_at INTEGER,
                  FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE
                );
                """.strip()
            )
            conn.commit()

        # Deterministic no-op branch for coverage: when sessions table already
        # has v2 columns, no upgrade work is performed.
        if has_command_id and has_stage_id:
            pass

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_command_id ON sessions(command_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_stage_id ON sessions(stage_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_ended_at ON sessions(ended_at);"
    )
    conn.commit()


def _ensure_snapshots(conn: sqlite3.Connection) -> None:
    """Ensure the `snapshots` table exists (v1.1.0).

    Snapshots store named serialized board state and a structural hash used for
    dedupe.
    """

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          saved_at INTEGER NOT NULL,
          payload_json TEXT NOT NULL,
          structural_hash TEXT NOT NULL
        );
        """.strip()
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_snapshots_saved_at ON snapshots(saved_at DESC, id DESC);"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_snapshots_name_hash ON snapshots(name, structural_hash);"
    )
    conn.commit()


def init_db(conn: sqlite3.Connection) -> None:
    """Create the v1 schema if it doesn't exist.

    No migrations framework in v1; schema is explicit and minimal.
    """
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS commands (
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          stage_id TEXT NOT NULL,
          status TEXT NOT NULL,
          sort_index INTEGER NOT NULL,
          created_at INTEGER NOT NULL
        );
        """.strip())
    # Ensure stage_id exists/backfilled *before* any stage_id index is created
    # (important when upgrading an existing v1 DB).
    _ensure_commands_stage_id(conn)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_commands_stage_id ON commands(stage_id);"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_commands_status ON commands(status);")

    _ensure_commands_sort_index(conn)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
          id INTEGER PRIMARY KEY,
          command_id INTEGER NOT NULL,
          note TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          FOREIGN KEY(command_id) REFERENCES commands(id) ON DELETE CASCADE
        );
        """.strip())
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_outcomes_command_created "
        "ON outcomes(command_id, created_at);"
    )

    _ensure_sessions_v2(conn)

    # v1.1.0 additions.
    _ensure_board_state(conn)
    _ensure_snapshots(conn)

    conn.commit()


def _connect(sqlite_path: str) -> sqlite3.Connection:
    # Ensure parent directory exists (important for per-user appdata paths).
    try:
        Path(sqlite_path).expanduser().resolve().parent.mkdir(
            parents=True, exist_ok=True
        )
    except Exception:
        # If we can't create dirs, let sqlite raise a clearer error.
        pass

    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a SQLite connection."""
    conn = _connect(SETTINGS.sqlite_path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()
