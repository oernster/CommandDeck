from __future__ import annotations

import sqlite3


class BoardRepository:
    """Persistence for singleton board state (name + naming flags)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self) -> dict[str, object]:
        row = self._conn.execute(
            "SELECT name, user_named, stage_labels_json, created_at FROM board_state WHERE id = 1"
        ).fetchone()
        if row is None:
            # Should not happen because schema ensure initializes row; fail loudly.
            raise RuntimeError("board_state row missing")
        return {
            "name": row[0],
            "user_named": int(row[1]),
            "stage_labels_json": row[2],
            "created_at": int(row[3]),
        }

    def exists(self) -> bool:
        row = self._conn.execute("SELECT 1 FROM board_state WHERE id = 1").fetchone()
        return row is not None

    def set_name(self, *, name: str | None) -> None:
        # NULL name is allowed; UI treats it as "Untitled board".
        self._conn.execute(
            "UPDATE board_state SET name = ?, user_named = 1 WHERE id = 1", (name,)
        )
        self._conn.commit()

    def is_empty(self) -> bool:
        """Return true if the live board has no persisted operational content."""

        cmds = int(self._conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0])
        sess = int(self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
        outs = int(self._conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0])
        return cmds == 0 and sess == 0 and outs == 0

    def reset_live_state(self) -> None:
        """Clear operational state for the single live board.

        Deletes outcomes, sessions and commands, but preserves the singleton
        `board_state` row, stage label overrides, and saved snapshots.
        """

        self._conn.execute("BEGIN")
        try:
            # Explicit deletes to match snapshot-load semantics and avoid relying
            # on FK cascade for user-visible behavior.
            self._conn.execute("DELETE FROM outcomes")
            self._conn.execute("DELETE FROM sessions")
            self._conn.execute("DELETE FROM commands")
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

