from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.schemas import BoardResponse, BoardUpdateRequest
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
    )

