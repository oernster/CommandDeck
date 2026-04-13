from __future__ import annotations

import json
from typing import cast

from app.repositories.board_repository import BoardRepository


class BoardService:
    def __init__(self, board: BoardRepository) -> None:
        self._board = board

    def get(self) -> dict[str, object]:
        row = self._board.get()

        name = cast(str | None, row["name"])
        user_named_int = cast(int, row["user_named"])
        stage_labels_json = cast(str | None, row.get("stage_labels_json"))
        created_at = cast(int, row["created_at"])

        user_named = bool(int(user_named_int))

        effective_name = (
            str(name) if name is not None and str(name).strip() else "Untitled board"
        )

        # "Newly created unnamed board" heuristic: user hasn't named it and it has
        # no operational content yet.
        is_new_unnamed = (not user_named) and self._board.is_empty()

        stage_labels: dict[str, str] | None = None
        if stage_labels_json is not None and str(stage_labels_json).strip():
            try:
                parsed = json.loads(str(stage_labels_json))
                if isinstance(parsed, dict) and all(
                    isinstance(k, str) and isinstance(v, str) for k, v in parsed.items()
                ):
                    stage_labels = cast(dict[str, str], parsed)
            except Exception:
                # Invalid persisted data should not break the board.
                stage_labels = None

        return {
            "name": effective_name,
            "user_named": user_named,
            "is_new_unnamed": is_new_unnamed,
            "stage_labels": stage_labels,
            "created_at": created_at,
        }

    def set_name(self, *, name: str) -> dict[str, object]:
        cleaned = name.strip()
        # Allow setting to empty string -> treat as NULL so default applies.
        self._board.set_name(name=(cleaned if cleaned else None))
        return self.get()

