from __future__ import annotations

import sqlite3

from app.domain.enums import Category, Status
from app.domain.models import Command


class CommandRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, category: Category | None, status: Status | None) -> list[Command]:
        sql = "SELECT id, title, category, status, created_at FROM commands"
        where: list[str] = []
        params: list[object] = []

        if category is not None:
            where.append("category = ?")
            params.append(category.value)
        if status is not None:
            where.append("status = ?")
            params.append(status.value)

        if where:
            sql += " WHERE " + " AND ".join(where)

        sql += " ORDER BY created_at DESC, id DESC"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_command(r) for r in rows]

    def get(self, command_id: int) -> Command | None:
        row = self._conn.execute(
            "SELECT id, title, category, status, created_at FROM commands WHERE id = ?",
            (command_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_command(row)

    def create(
        self, title: str, category: Category, status: Status, created_at: int
    ) -> Command:
        self._conn.execute(
            "INSERT INTO commands (title, category, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            (title, category.value, status.value, created_at),
        )
        self._conn.commit()

        # `Cursor.lastrowid` is typed as Optional[int]; in practice SQLite always
        # provides this for successful inserts, but we avoid a defensive branch
        # (which is hard to reproduce without mocking).
        command_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Command(
            id=command_id,
            title=title,
            category=category,
            status=status,
            created_at=created_at,
        )

    def update(
        self,
        command_id: int,
        title: str | None,
        category: Category | None,
        status: Status | None,
    ) -> Command | None:
        existing = self.get(command_id)
        if existing is None:
            return None

        new_title = title if title is not None else existing.title
        new_category = category if category is not None else existing.category
        new_status = status if status is not None else existing.status

        self._conn.execute(
            "UPDATE commands SET title = ?, category = ?, status = ? WHERE id = ?",
            (new_title, new_category.value, new_status.value, command_id),
        )
        self._conn.commit()
        return Command(
            id=existing.id,
            title=new_title,
            category=new_category,
            status=new_status,
            created_at=existing.created_at,
        )

    def delete(self, command_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM commands WHERE id = ?", (command_id,))
        self._conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def _row_to_command(row: sqlite3.Row) -> Command:
        category = Category.from_str(row["category"])
        status = Status.from_str(row["status"])
        if category is None or status is None:
            # Data corruption shouldn't happen in v1; raise explicit error.
            raise ValueError("Invalid enum value in database")

        return Command(
            id=int(row["id"]),
            title=str(row["title"]),
            category=category,
            status=status,
            created_at=int(row["created_at"]),
        )
