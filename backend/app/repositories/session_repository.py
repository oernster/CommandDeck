from __future__ import annotations

import sqlite3

from app.domain.enums import StageId
from app.domain.models import Session


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, stage_id: StageId | None, active: bool | None) -> list[Session]:
        sql = "SELECT id, command_id, stage_id, started_at, ended_at FROM sessions"
        where: list[str] = []
        params: list[object] = []

        if stage_id is not None:
            where.append("stage_id = ?")
            params.append(stage_id.value)
        if active is True:
            where.append("ended_at IS NULL")
        if active is False:
            where.append("ended_at IS NOT NULL")

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY started_at DESC, id DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_active(self) -> Session | None:
        row = self._conn.execute("""
            SELECT id, command_id, stage_id, started_at, ended_at
            FROM sessions
            WHERE ended_at IS NULL
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """.strip()).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def latest_by_stage_id(self) -> list[Session]:
        """Return the latest session per stage.

        Note: SQLite doesn't have a great portable DISTINCT ON equivalent. This
        implementation uses ordering (latest first) and reduces in Python.
        """
        rows = self._conn.execute("""
            SELECT id, command_id, stage_id, started_at, ended_at
            FROM sessions
            ORDER BY started_at DESC, id DESC
            """.strip()).fetchall()

        latest: dict[str, Session] = {}
        for r in rows:
            s = self._row_to_session(r)
            # Rows are ordered newest-first, so first time we see a stage is its
            # latest session.
            if s.stage_id.value not in latest:
                latest[s.stage_id.value] = s

        return list(latest.values())

    def start(self, command_id: int, stage_id: StageId, now_epoch_seconds: int) -> Session:
        """Stop any active session and start a new one in a single transaction."""
        self._conn.execute("BEGIN")
        try:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL",
                (now_epoch_seconds,),
            )
            self._conn.execute(
                "INSERT INTO sessions (command_id, stage_id, started_at, ended_at) "
                "VALUES (?, ?, ?, NULL)",
                (command_id, stage_id.value, now_epoch_seconds),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        session_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Session(
            id=session_id,
            command_id=command_id,
            stage_id=stage_id,
            started_at=now_epoch_seconds,
            ended_at=None,
        )

    def stop(self, now_epoch_seconds: int) -> Session | None:
        active = self.get_active()
        if active is None:
            return None

        self._conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (now_epoch_seconds, active.id),
        )
        self._conn.commit()
        return Session(
            id=active.id,
            command_id=active.command_id,
            stage_id=active.stage_id,
            started_at=active.started_at,
            ended_at=now_epoch_seconds,
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        stage_id = StageId.from_str(row["stage_id"])
        if stage_id is None:
            raise ValueError("Invalid enum value in database")
        ended_at = row["ended_at"]
        return Session(
            id=int(row["id"]),
            command_id=int(row["command_id"]),
            stage_id=stage_id,
            started_at=int(row["started_at"]),
            ended_at=int(ended_at) if ended_at is not None else None,
        )
