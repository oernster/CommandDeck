from __future__ import annotations

import sqlite3

from typing import TypedDict


class SnapshotSummaryRow(TypedDict):
    id: int
    name: str
    saved_at: int


class SnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self) -> list[SnapshotSummaryRow]:
        rows = self._conn.execute(
            "SELECT id, name, saved_at FROM snapshots ORDER BY saved_at DESC, id DESC"
        ).fetchall()
        return [
            {"id": int(r[0]), "name": str(r[1]), "saved_at": int(r[2])} for r in rows
        ]

    def get_payload(self, snapshot_id: int) -> dict[str, object] | None:
        row = self._conn.execute(
            "SELECT id, name, saved_at, payload_json, structural_hash FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": int(row[0]),
            "name": str(row[1]),
            "saved_at": int(row[2]),
            "payload_json": str(row[3]),
            "structural_hash": str(row[4]),
        }

    def exists(self, snapshot_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        return row is not None

    def upsert_by_name_hash(
        self,
        *,
        name: str,
        structural_hash: str,
        saved_at: int,
        payload_json: str,
    ) -> SnapshotSummaryRow:
        """Insert or update by (name, structural_hash) to enforce dedupe."""

        self._conn.execute("BEGIN")
        try:
            existing = self._conn.execute(
                "SELECT id FROM snapshots WHERE name = ? AND structural_hash = ?",
                (name, structural_hash),
            ).fetchone()
            if existing is None:
                self._conn.execute(
                    "INSERT INTO snapshots (name, saved_at, payload_json, structural_hash) VALUES (?, ?, ?, ?)",
                    (name, saved_at, payload_json, structural_hash),
                )
                snapshot_id = int(
                    self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                )
            else:
                snapshot_id = int(existing[0])
                self._conn.execute(
                    "UPDATE snapshots SET saved_at = ?, payload_json = ? WHERE id = ?",
                    (saved_at, payload_json, snapshot_id),
                )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

        return {"id": snapshot_id, "name": name, "saved_at": saved_at}

    def find_latest_by_structural_hash(
        self, structural_hash: str
    ) -> SnapshotSummaryRow | None:
        row = self._conn.execute(
            "SELECT id, name, saved_at FROM snapshots WHERE structural_hash = ? ORDER BY saved_at DESC, id DESC LIMIT 1",
            (structural_hash,),
        ).fetchone()
        if row is None:
            return None
        return {"id": int(row[0]), "name": str(row[1]), "saved_at": int(row[2])}

    def insert(
        self,
        *,
        name: str,
        structural_hash: str,
        saved_at: int,
        payload_json: str,
    ) -> SnapshotSummaryRow:
        self._conn.execute(
            "INSERT INTO snapshots (name, saved_at, payload_json, structural_hash) VALUES (?, ?, ?, ?)",
            (name, saved_at, payload_json, structural_hash),
        )
        self._conn.commit()
        snapshot_id = int(self._conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        return {"id": snapshot_id, "name": name, "saved_at": saved_at}

    def update_payload(self, *, snapshot_id: int, saved_at: int, payload_json: str) -> None:
        self._conn.execute(
            "UPDATE snapshots SET saved_at = ?, payload_json = ? WHERE id = ?",
            (saved_at, payload_json, snapshot_id),
        )
        self._conn.commit()

    def update_name(self, *, snapshot_id: int, name: str) -> None:
        self._conn.execute(
            "UPDATE snapshots SET name = ? WHERE id = ?",
            (name, snapshot_id),
        )
        self._conn.commit()

    def get_summary(self, snapshot_id: int) -> SnapshotSummaryRow | None:
        row = self._conn.execute(
            "SELECT id, name, saved_at FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            return None
        return {"id": int(row[0]), "name": str(row[1]), "saved_at": int(row[2])}

