from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.enums import Category
from app.domain.errors import ValidationError
from app.domain.schemas import (
    SessionLatestByCategory,
    SessionResponse,
    SessionStartRequest,
)
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> SessionService:
    return SessionService(SessionRepository(conn))


@router.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(
    category: str | None = None,
    active: bool | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[SessionResponse]:
    parsed_category = None
    if category is not None:
        parsed_category = Category.from_str(category)
        if parsed_category is None:
            raise ValidationError("Invalid category")

    service = _service(conn)
    sessions = service.list(category=parsed_category, active=active)
    return [SessionResponse.from_model(s) for s in sessions]


@router.get("/api/sessions/active")
def get_active_session(
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionResponse | dict[str, bool]:
    service = _service(conn)
    session = service.get_active()
    if session is None:
        return {"active": False}
    return SessionResponse.from_model(session)


@router.get("/api/sessions/latest-by-category", response_model=SessionLatestByCategory)
def latest_by_category(
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionLatestByCategory:
    """Return the latest session (active or ended) for every category.

    Categories with no sessions are returned with a null value.
    """
    service = _service(conn)
    latest = service.latest_by_category()

    out: SessionLatestByCategory = {}
    for c in Category:
        session = latest.get(c)
        out[c.value] = SessionResponse.from_model(session) if session else None
    return out


@router.post("/api/sessions/start", response_model=SessionResponse)
def start_session(
    payload: SessionStartRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionResponse:
    parsed = Category.from_str(payload.category)
    if parsed is None:
        raise ValidationError("Invalid category")

    service = _service(conn)
    session = service.start(category=parsed)
    return SessionResponse.from_model(session)


@router.post("/api/sessions/stop")
def stop_session(
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionResponse | dict[str, bool]:
    service = _service(conn)
    stopped = service.stop()
    if stopped is None:
        return {"active": False}
    return SessionResponse.from_model(stopped)
