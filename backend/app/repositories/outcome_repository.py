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

    def latest_and_counts_for_commands(
        self, command_ids: list[int]
    ) -> tuple[dict[int, Outcome], dict[int, int]]:
        """Return (latest outcome per command, total outcome counts per command).

        Only returns entries for command_ids that have at least one outcome.
        """

        if not command_ids:
            return {}, {}

        placeholders = ",".join(["?"] * len(command_ids))
        rows = self._conn.execute(
            f"""
            SELECT id, command_id, note, created_at, total_count
            FROM (
              SELECT
                o.id,
                o.command_id,
                o.note,
                o.created_at,
                COUNT(*) OVER (PARTITION BY o.command_id) AS total_count,
                ROW_NUMBER() OVER (
                  PARTITION BY o.command_id
                  ORDER BY o.created_at DESC, o.id DESC
                ) AS rn
              FROM outcomes o
              WHERE o.command_id IN ({placeholders})
            )
            WHERE rn = 1;
            """,
            tuple(command_ids),
        ).fetchall()

        latest: dict[int, Outcome] = {}
        counts: dict[int, int] = {}
        for r in rows:
            o = self._row_to_outcome(r)
            latest[o.command_id] = o
            counts[o.command_id] = int(r["total_count"])
        return latest, counts

    def list_for_commands(self, command_ids: list[int]) -> dict[int, list[Outcome]]:
        """Return outcomes grouped by command_id (newest-first per command).

        Only returns entries for command_ids that have at least one outcome.
        """

        if not command_ids:
            return {}

        placeholders = ",".join(["?"] * len(command_ids))
        rows = self._conn.execute(
            f"""
            SELECT id, command_id, note, created_at
            FROM outcomes
            WHERE command_id IN ({placeholders})
            ORDER BY command_id ASC, created_at DESC, id DESC
            """.strip(),
            tuple(command_ids),
        ).fetchall()

        out: dict[int, list[Outcome]] = {}
        for r in rows:
            o = self._row_to_outcome(r)
            out.setdefault(o.command_id, []).append(o)
        return out

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
