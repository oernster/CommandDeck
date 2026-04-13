from __future__ import annotations

import sqlite3
from typing import cast

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.schemas import BoardResponse, BoardUpdateRequest, StageLabelsUpdateRequest
from app.repositories.board_repository import BoardRepository
from app.services.board_service import BoardService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> BoardService:
    return BoardService(BoardRepository(conn))


@router.get("/api/board", response_model=BoardResponse)
def get_board(conn: sqlite3.Connection = Depends(get_db)) -> BoardResponse:
    service = _service(conn)
    data = service.get()
    return BoardResponse(
        name=str(data["name"]),
        user_named=bool(data["user_named"]),
        is_new_unnamed=bool(data["is_new_unnamed"]),
        is_empty=bool(data["is_empty"]),
        stage_labels=cast(dict[str, str] | None, data.get("stage_labels")),
    )


@router.patch("/api/board", response_model=BoardResponse)
def update_board(
    payload: BoardUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> BoardResponse:
    service = _service(conn)
    data = service.set_name(name=payload.name)
    return BoardResponse(
        name=str(data["name"]),
        user_named=bool(data["user_named"]),
        is_new_unnamed=bool(data["is_new_unnamed"]),
        is_empty=bool(data["is_empty"]),
        stage_labels=cast(dict[str, str] | None, data.get("stage_labels")),
    )


@router.patch("/api/board/stage-labels", response_model=BoardResponse)
def update_stage_labels(
    payload: StageLabelsUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> BoardResponse:
    # Persist labels as a JSON blob on board_state.
    # Coverage note: the request/response flow is exercised in tests.
    conn.execute(
        "UPDATE board_state SET stage_labels_json = ? WHERE id = 1",
        (__import__("json").dumps(payload.stage_labels, separators=(",", ":")),),
    )
    conn.commit()

    service = _service(conn)
    data = service.get()
    return BoardResponse(
        name=str(data["name"]),
        user_named=bool(data["user_named"]),
        is_new_unnamed=bool(data["is_new_unnamed"]),
        is_empty=bool(data["is_empty"]),
        stage_labels=cast(dict[str, str] | None, data.get("stage_labels")),
    )


@router.post("/api/board/reset")
def reset_board(conn: sqlite3.Connection = Depends(get_db)) -> dict[str, bool]:
    service = _service(conn)
    service.reset()
    return {"ok": True}

