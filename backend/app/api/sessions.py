from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.enums import StageId
from app.domain.errors import ValidationError
from app.domain.schemas import (
    SessionLatestByStageId,
    SessionResponse,
    SessionStartRequest,
)
from app.repositories.command_repository import CommandRepository
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> SessionService:
    return SessionService(SessionRepository(conn))


@router.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(
    stage_id: str | None = None,
    active: bool | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[SessionResponse]:
    parsed_stage_id = None
    if stage_id is not None:
        parsed_stage_id = StageId.from_str(stage_id)
        if parsed_stage_id is None:
            raise ValidationError("Invalid stage_id")

    service = _service(conn)
    sessions = service.list(stage_id=parsed_stage_id, active=active)
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


@router.get("/api/sessions/latest-by-stage-id", response_model=SessionLatestByStageId)
def latest_by_stage_id(
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionLatestByStageId:
    """Return the latest session (active or ended) for every stage.

    Categories with no sessions are returned with a null value.
    """
    service = _service(conn)
    latest = service.latest_by_stage_id()

    out: SessionLatestByStageId = {}
    for s in StageId:
        session = latest.get(s)
        out[s.value] = SessionResponse.from_model(session) if session else None
    return out


@router.post("/api/sessions/start", response_model=SessionResponse)
def start_session(
    payload: SessionStartRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> SessionResponse:
    # Start requires task selection: validate command exists and derive its stage.
    cmd_repo = CommandRepository(conn)
    cmd = cmd_repo.get(int(payload.command_id))
    if cmd is None:
        raise ValidationError("Invalid command_id")

    service = _service(conn)
    session = service.start(command_id=cmd.id, stage_id=cmd.stage_id)
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
