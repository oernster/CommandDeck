from __future__ import annotations

import sqlite3


class SnapshotRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list(self) -> list[dict[str, object]]:
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
    ) -> dict[str, object]:
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

