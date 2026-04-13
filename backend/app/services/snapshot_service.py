from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from typing import Any

from app.domain.enums import Category, Status
from app.domain.errors import NotFoundError
from app.repositories.board_repository import BoardRepository
from app.repositories.snapshot_repository import SnapshotRepository


class SnapshotService:
    """Create/list/load named board snapshots.

    Snapshots are additional optional memory layered on top of the existing
    live-board persistence.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        conn: sqlite3.Connection,
        board: BoardRepository,
        snapshots: SnapshotRepository,
    ) -> None:
        self._conn = conn
        self._board = board
        self._snapshots = snapshots

    def list(self) -> list[dict[str, object]]:
        return self._snapshots.list()

    def save_now(self) -> dict[str, object]:
        """Serialize current DB state and upsert a snapshot with dedupe."""

        now_epoch_seconds = int(
            self._conn.execute("SELECT CAST(strftime('%s','now') AS INTEGER)").fetchone()[
                0
            ]
        )
        board_row = self._board.get()
        name = board_row["name"]
        board_name = (
            str(name) if name is not None and str(name).strip() else "Untitled board"
        )

        payload = self._serialize_payload(board_name=board_name, saved_at=now_epoch_seconds)
        structural = self._structural_form(payload)

        payload_json = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        structural_json = json.dumps(
            structural, separators=(",", ":"), sort_keys=True, ensure_ascii=False
        )
        structural_hash = hashlib.sha256(structural_json.encode("utf-8")).hexdigest()

        return self._snapshots.upsert_by_name_hash(
            name=board_name,
            structural_hash=structural_hash,
            saved_at=now_epoch_seconds,
            payload_json=payload_json,
        )

    def load(self, *, snapshot_id: int) -> None:
        row = self._snapshots.get_payload(snapshot_id)
        if row is None:
            raise NotFoundError("Snapshot not found")

        payload = json.loads(str(row["payload_json"]))
        self._apply_payload(payload)

    def _serialize_payload(self, *, board_name: str, saved_at: int) -> dict[str, Any]:
        # Commands: ordered by category+sort_index already.
        rows = self._conn.execute(
            "SELECT title, category, status FROM commands ORDER BY category ASC, sort_index ASC, id ASC"
        ).fetchall()

        by_category: dict[str, list[dict[str, str]]] = {c.value: [] for c in Category}
        for r in rows:
            by_category[str(r["category"])].append(
                {"title": str(r["title"]), "status": str(r["status"])}
            )

        # Sessions: include full list (newest-first) so we can restore timing if desired.
        srows = self._conn.execute(
            "SELECT category, started_at, ended_at FROM sessions ORDER BY started_at DESC, id DESC"
        ).fetchall()
        sessions = [
            {
                "category": str(r["category"]),
                "started_at": int(r["started_at"]),
                "ended_at": (int(r["ended_at"]) if r["ended_at"] is not None else None),
            }
            for r in srows
        ]

        return {
            "schema_version": self.SCHEMA_VERSION,
            "board_name": board_name,
            "saved_at": saved_at,
            "commands": by_category,
            "sessions": sessions,
        }

    @staticmethod
    def _structural_form(payload: dict[str, Any]) -> dict[str, Any]:
        """Return canonical structural form used for dedupe.

        Includes operational structure + name, excludes runtime-only timestamps.
        """

        sessions = payload.get("sessions") or []
        active_session_category = None
        for s in sessions:
            if isinstance(s, dict) and s.get("ended_at") is None:
                active_session_category = s.get("category")
                break

        return {
            "schema_version": int(payload.get("schema_version", 1)),
            "board_name": str(payload.get("board_name") or "Untitled board"),
            "active_session_category": active_session_category,
            "commands": payload.get("commands") or {},
        }

    def _apply_payload(self, payload: dict[str, Any]) -> None:
        # Validate minimal schema.
        if int(payload.get("schema_version", 0)) != self.SCHEMA_VERSION:
            raise ValueError("Unsupported snapshot schema")

        # Defensive: name must exist (used in dedupe identity rules and UI).
        if not str(payload.get("board_name") or "").strip():
            raise ValueError("Invalid snapshot payload")

        commands = payload.get("commands")
        if not isinstance(commands, dict):
            raise ValueError("Invalid snapshot payload")

        sessions = payload.get("sessions")
        if sessions is None:
            raise ValueError("Invalid snapshot payload")
        if not isinstance(sessions, list):
            raise ValueError("Invalid snapshot payload")

        # Optional safety: ensure the singleton board_state exists.
        if not self._board.exists():
            raise RuntimeError("board_state missing")

        # Apply in a single transaction: clear outcomes, then sessions, then commands.
        now_epoch_seconds = int(
            self._conn.execute("SELECT CAST(strftime('%s','now') AS INTEGER)").fetchone()[0]
        )
        self._conn.execute("BEGIN")
        try:
            self._conn.execute("DELETE FROM outcomes")
            self._conn.execute("DELETE FROM sessions")
            self._conn.execute("DELETE FROM commands")

            # Insert commands with deterministic sort_index per category.
            sort_index_by_cat: dict[str, int] = defaultdict(int)
            for cat in Category:
                items = commands.get(cat.value, [])
                if items is None:
                    raise ValueError("Invalid snapshot payload")
                if not isinstance(items, list):
                    raise ValueError("Invalid snapshot payload")

                # Explicit no-op branch for 100% coverage while preserving clarity.
                if len(items) == 0:
                    continue

                for entry in items:
                    if not isinstance(entry, dict):
                        raise ValueError("Invalid snapshot payload")
                    title = str(entry.get("title") or "").strip()
                    status_str = str(entry.get("status") or "")
                    if not title:
                        raise ValueError("Invalid snapshot payload")
                    if Status.from_str(status_str) is None:
                        raise ValueError("Invalid snapshot payload")

                    sort_index_by_cat[cat.value] += 1
                    self._conn.execute(
                        "INSERT INTO commands (title, category, status, sort_index, created_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            title,
                            cat.value,
                            status_str,
                            sort_index_by_cat[cat.value],
                            now_epoch_seconds,
                        ),
                    )

            # Insert sessions; enforce at most one active session.
            active_seen = False
            for s in sessions:
                if not isinstance(s, dict):
                    raise ValueError("Invalid snapshot payload")
                category_str = str(s.get("category") or "")
                if Category.from_str(category_str) is None:
                    raise ValueError("Invalid snapshot payload")
                started_at = s.get("started_at")
                ended_at = s.get("ended_at")
                if not isinstance(started_at, int):
                    raise ValueError("Invalid snapshot payload")
                if ended_at is not None and not isinstance(ended_at, int):
                    raise ValueError("Invalid snapshot payload")
                if ended_at is None:
                    if active_seen:
                        # Keep deterministic behavior: only the first active session wins.
                        continue
                    active_seen = True

                self._conn.execute(
                    "INSERT INTO sessions (category, started_at, ended_at) VALUES (?, ?, ?)",
                    (category_str, started_at, ended_at),
                )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

