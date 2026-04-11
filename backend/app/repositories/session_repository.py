from __future__ import annotations

import sqlite3

from app.domain.enums import Category
from app.domain.models import Session


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, category: Category | None, active: bool | None) -> list[Session]:
        sql = "SELECT id, category, started_at, ended_at FROM sessions"
        where: list[str] = []
        params: list[object] = []

        if category is not None:
            where.append("category = ?")
            params.append(category.value)
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
            SELECT id, category, started_at, ended_at
            FROM sessions
            WHERE ended_at IS NULL
            ORDER BY started_at DESC, id DESC
            LIMIT 1
            """.strip()).fetchone()
        if row is None:
            return None
        return self._row_to_session(row)

    def start(self, category: Category, now_epoch_seconds: int) -> Session:
        """Stop any active session and start a new one in a single transaction."""
        self._conn.execute("BEGIN")
        try:
            self._conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE ended_at IS NULL",
                (now_epoch_seconds,),
            )
            self._conn.execute(
                "INSERT INTO sessions (category, started_at, ended_at) "
                "VALUES (?, ?, NULL)",
                (category.value, now_epoch_seconds),
            )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        session_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Session(
            id=session_id,
            category=category,
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
            category=active.category,
            started_at=active.started_at,
            ended_at=now_epoch_seconds,
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        category = Category.from_str(row["category"])
        if category is None:
            raise ValueError("Invalid enum value in database")
        ended_at = row["ended_at"]
        return Session(
            id=int(row["id"]),
            category=category,
            started_at=int(row["started_at"]),
            ended_at=int(ended_at) if ended_at is not None else None,
        )
