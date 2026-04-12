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

        # Commands are ordered per category via sort_index (persisted).
        # Include category for stable global listing; within a category we use
        # sort_index (and created_at/id only as deterministic tie-breakers).
        sql += " ORDER BY category ASC, sort_index ASC, created_at ASC, id ASC"

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
        # Newest commands should appear at the bottom of their category column.
        next_sort = int(
            self._conn.execute(
                "SELECT COALESCE(MAX(sort_index), 0) + 1 FROM commands WHERE category = ?",
                (category.value,),
            ).fetchone()[0]
        )
        self._conn.execute(
            "INSERT INTO commands (title, category, status, sort_index, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, category.value, status.value, next_sort, created_at),
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

        # If the category changed via an update, append to bottom of the new column.
        if new_category != existing.category:
            next_sort = int(
                self._conn.execute(
                    "SELECT COALESCE(MAX(sort_index), 0) + 1 FROM commands WHERE category = ?",
                    (new_category.value,),
                ).fetchone()[0]
            )
            self._conn.execute(
                "UPDATE commands SET title = ?, category = ?, status = ?, sort_index = ? WHERE id = ?",
                (new_title, new_category.value, new_status.value, next_sort, command_id),
            )
        else:
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

    def reorder(self, by_category: dict[Category, list[int]]) -> None:
        """Persist a complete ordering for one or more categories.

        Expects each category list to contain every existing command id for that
        category exactly once.
        """

        self._conn.execute("BEGIN")
        try:
            # Validate that the payload includes each command exactly once across
            # the involved categories, and that it matches the current DB coverage
            # for those categories.
            payload_ids: list[int] = []
            for ids in by_category.values():
                payload_ids.extend(ids)

            if len(payload_ids) != len(set(payload_ids)):
                raise ValueError("Reorder payload contains duplicate command ids")

            involved_categories = [c.value for c in by_category.keys()]
            if involved_categories:
                placeholders = ",".join(["?"] * len(involved_categories))
                existing_rows = self._conn.execute(
                    f"SELECT id FROM commands WHERE category IN ({placeholders})",
                    involved_categories,
                ).fetchall()
                existing_ids = [int(r[0]) for r in existing_rows]
            else:
                existing_ids = []

            if sorted(existing_ids) != sorted(payload_ids):
                raise ValueError(
                    "Reorder payload must include exactly all command ids for the affected categories"
                )

            # Apply final category + order.
            for category, ids in by_category.items():
                for idx, cmd_id in enumerate(ids, start=1):
                    self._conn.execute(
                        "UPDATE commands SET category = ?, sort_index = ? WHERE id = ?",
                        (category.value, idx, cmd_id),
                    )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

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
