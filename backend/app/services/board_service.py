from __future__ import annotations

from typing import cast

from app.repositories.board_repository import BoardRepository


class BoardService:
    def __init__(self, board: BoardRepository) -> None:
        self._board = board

    def get(self) -> dict[str, object]:
        row = self._board.get()

        name = cast(str | None, row["name"])
        user_named_int = cast(int, row["user_named"])
        created_at = cast(int, row["created_at"])

        user_named = bool(int(user_named_int))

        effective_name = (
            str(name) if name is not None and str(name).strip() else "Untitled board"
        )

        # "Newly created unnamed board" heuristic: user hasn't named it and it has
        # no operational content yet.
        is_new_unnamed = (not user_named) and self._board.is_empty()

        return {
            "name": effective_name,
            "user_named": user_named,
            "is_new_unnamed": is_new_unnamed,
            "created_at": created_at,
        }

    def set_name(self, *, name: str) -> dict[str, object]:
        cleaned = name.strip()
        # Allow setting to empty string -> treat as NULL so default applies.
        self._board.set_name(name=(cleaned if cleaned else None))
        return self.get()

