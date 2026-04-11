from __future__ import annotations

import sqlite3

from app.domain.enums import Category
from app.domain.models import Session


class SessionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, category: Category | None, active: bool | None) -> list[Session]:
        sql = "SELECT id, category, start_time, end_time FROM sessions"
        where: list[str] = []
        params: list[object] = []

        if category is not None:
            where.append("category = ?")
            params.append(category.value)
        if active is True:
            where.append("end_time IS NULL")
        if active is False:
            where.append("end_time IS NOT NULL")

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY start_time DESC, id DESC"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_session(r) for r in rows]

    def get_active(self) -> Session | None:
        row = self._conn.execute("""
            SELECT id, category, start_time, end_time
            FROM sessions
            WHERE end_time IS NULL
            ORDER BY start_time DESC, id DESC
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
                "UPDATE sessions SET end_time = ? WHERE end_time IS NULL",
                (now_epoch_seconds,),
            )
            self._conn.execute(
                "INSERT INTO sessions (category, start_time, end_time) "
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
            start_time=now_epoch_seconds,
            end_time=None,
        )

    def stop(self, now_epoch_seconds: int) -> Session | None:
        active = self.get_active()
        if active is None:
            return None

        self._conn.execute(
            "UPDATE sessions SET end_time = ? WHERE id = ?",
            (now_epoch_seconds, active.id),
        )
        self._conn.commit()
        return Session(
            id=active.id,
            category=active.category,
            start_time=active.start_time,
            end_time=now_epoch_seconds,
        )

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> Session:
        category = Category.from_str(row["category"])
        if category is None:
            raise ValueError("Invalid enum value in database")
        end_time = row["end_time"]
        return Session(
            id=int(row["id"]),
            category=category,
            start_time=int(row["start_time"]),
            end_time=int(end_time) if end_time is not None else None,
        )
