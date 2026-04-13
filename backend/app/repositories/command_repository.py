from __future__ import annotations

import sqlite3

from app.domain.enums import StageId, Status
from app.domain.models import Command


class CommandRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self, stage_id: StageId | None, status: Status | None) -> list[Command]:
        sql = "SELECT id, title, stage_id, status, created_at FROM commands"
        where: list[str] = []
        params: list[object] = []

        if stage_id is not None:
            where.append("stage_id = ?")
            params.append(stage_id.value)
        if status is not None:
            where.append("status = ?")
            params.append(status.value)

        if where:
            sql += " WHERE " + " AND ".join(where)

        # Commands are ordered per stage via sort_index (persisted).
        # Include stage_id for stable global listing; within a stage we use
        # sort_index (and created_at/id only as deterministic tie-breakers).
        sql += " ORDER BY stage_id ASC, sort_index ASC, created_at ASC, id ASC"

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_command(r) for r in rows]

    def get(self, command_id: int) -> Command | None:
        row = self._conn.execute(
            "SELECT id, title, stage_id, status, created_at FROM commands WHERE id = ?",
            (command_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_command(row)

    def create(
        self, title: str, stage_id: StageId, status: Status, created_at: int
    ) -> Command:
        # Newest commands should appear at the bottom of their category column.
        next_sort = int(
            self._conn.execute(
                (
                    "SELECT COALESCE(MAX(sort_index), 0) + 1 "
                    "FROM commands WHERE stage_id = ?"
                ),
                (stage_id.value,),
            ).fetchone()[0]
        )
        self._conn.execute(
            "INSERT INTO commands (title, stage_id, status, sort_index, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (title, stage_id.value, status.value, next_sort, created_at),
        )
        self._conn.commit()

        # `Cursor.lastrowid` is typed as Optional[int]; in practice SQLite always
        # provides this for successful inserts, but we avoid a defensive branch
        # (which is hard to reproduce without mocking).
        command_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return Command(
            id=command_id,
            title=title,
            stage_id=stage_id,
            status=status,
            created_at=created_at,
        )

    def update(
        self,
        command_id: int,
        title: str | None,
        stage_id: StageId | None,
        status: Status | None,
    ) -> Command | None:
        existing = self.get(command_id)
        if existing is None:
            return None

        new_title = title if title is not None else existing.title
        new_stage_id = stage_id if stage_id is not None else existing.stage_id
        new_status = status if status is not None else existing.status

        # If the category changed via an update, append to bottom of the new column.
        if new_stage_id != existing.stage_id:
            next_sort = int(
                self._conn.execute(
                    (
                        "SELECT COALESCE(MAX(sort_index), 0) + 1 "
                        "FROM commands WHERE stage_id = ?"
                    ),
                    (new_stage_id.value,),
                ).fetchone()[0]
            )
            self._conn.execute(
                (
                    "UPDATE commands SET title = ?, stage_id = ?, status = ?, "
                    "sort_index = ? "
                    "WHERE id = ?"
                ),
                (
                    new_title,
                    new_stage_id.value,
                    new_status.value,
                    next_sort,
                    command_id,
                ),
            )
        else:
            self._conn.execute(
                "UPDATE commands SET title = ?, stage_id = ?, status = ? WHERE id = ?",
                (new_title, new_stage_id.value, new_status.value, command_id),
            )
        self._conn.commit()
        return Command(
            id=existing.id,
            title=new_title,
            stage_id=new_stage_id,
            status=new_status,
            created_at=existing.created_at,
        )

    def delete(self, command_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM commands WHERE id = ?", (command_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def reorder(self, by_stage_id: dict[StageId, list[int]]) -> None:
        """Persist a complete ordering for one or more stages.

        Expects each category list to contain every existing command id for that
        category exactly once.
        """

        self._conn.execute("BEGIN")
        try:
            # Validate that the payload includes each command exactly once across
            # the involved categories, and that it matches the current DB coverage
            # for those categories.
            payload_ids: list[int] = []
            for ids in by_stage_id.values():
                payload_ids.extend(ids)

            if len(payload_ids) != len(set(payload_ids)):
                raise ValueError("Reorder payload contains duplicate command ids")

            involved_stages = [s.value for s in by_stage_id.keys()]
            if involved_stages:
                placeholders = ",".join(["?"] * len(involved_stages))
                existing_rows = self._conn.execute(
                    f"SELECT id FROM commands WHERE stage_id IN ({placeholders})",
                    involved_stages,
                ).fetchall()
                existing_ids = [int(r[0]) for r in existing_rows]
            else:
                existing_ids = []

            if sorted(existing_ids) != sorted(payload_ids):
                raise ValueError(
                    "Reorder payload must include exactly all command ids for the "
                    "affected stages"
                )

            # Apply final stage + order.
            for stage_id, ids in by_stage_id.items():
                for idx, cmd_id in enumerate(ids, start=1):
                    self._conn.execute(
                        "UPDATE commands SET stage_id = ?, sort_index = ? WHERE id = ?",
                        (stage_id.value, idx, cmd_id),
                    )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    @staticmethod
    def _row_to_command(row: sqlite3.Row) -> Command:
        stage_id = StageId.from_str(row["stage_id"])
        status = Status.from_str(row["status"])
        if stage_id is None or status is None:
            # Data corruption shouldn't happen in v1; raise explicit error.
            raise ValueError("Invalid enum value in database")

        return Command(
            id=int(row["id"]),
            title=str(row["title"]),
            stage_id=stage_id,
            status=status,
            created_at=int(row["created_at"]),
        )
