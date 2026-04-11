from __future__ import annotations

import sqlite3

from app.domain.models import Outcome


class OutcomeRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_for_command(self, command_id: int) -> list[Outcome]:
        rows = self._conn.execute(
            """
            SELECT id, command_id, note, created_at
            FROM outcomes
            WHERE command_id = ?
            ORDER BY created_at DESC, id DESC
            """.strip(),
            (command_id,),
        ).fetchall()
        return [self._row_to_outcome(r) for r in rows]

    def create(self, command_id: int, note: str, created_at: int) -> Outcome:
        self._conn.execute(
            "INSERT INTO outcomes (command_id, note, created_at) VALUES (?, ?, ?)",
            (command_id, note, created_at),
        )
        self._conn.commit()
        outcome_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Outcome(
            id=outcome_id,
            command_id=command_id,
            note=note,
            created_at=created_at,
        )

    def delete(self, outcome_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM outcomes WHERE id = ?", (outcome_id,))
        self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_outcome(row: sqlite3.Row) -> Outcome:
        return Outcome(
            id=int(row["id"]),
            command_id=int(row["command_id"]),
            note=str(row["note"]),
            created_at=int(row["created_at"]),
        )
