from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.enums import StageId, Status
from app.domain.errors import NotFoundError, ValidationError
from app.domain.schemas import (
    CommandCreateRequest,
    CommandReorderRequest,
    CommandResponse,
    CommandUpdateRequest,
)
from app.repositories.command_repository import CommandRepository
from app.services.command_service import CommandService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> CommandService:
    return CommandService(CommandRepository(conn))


@router.get("/api/commands", response_model=list[CommandResponse])
def list_commands(
    stage_id: str | None = None,
    status: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[CommandResponse]:
    parsed_stage_id = None
    if stage_id is not None:
        parsed_stage_id = StageId.from_str(stage_id)
        if parsed_stage_id is None:
            raise ValidationError("Invalid stage_id")

    parsed_status = None
    if status is not None:
        parsed_status = Status.from_str(status)
        if parsed_status is None:
            raise ValidationError("Invalid status")

    service = _service(conn)
    return [
        CommandResponse.from_model(c)
        for c in service.list(parsed_stage_id, parsed_status)
    ]


@router.post("/api/commands", response_model=CommandResponse, status_code=201)
def create_command(
    payload: CommandCreateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> CommandResponse:
    parsed_stage_id = StageId.from_str(payload.stage_id)
    if parsed_stage_id is None:
        raise ValidationError("Invalid stage_id")

    parsed_status = Status.NOT_STARTED
    if payload.status is not None:
        maybe_status = Status.from_str(payload.status)
        if maybe_status is None:
            raise ValidationError("Invalid status")
        parsed_status = maybe_status

    service = _service(conn)
    cmd = service.create(
        title=payload.title,
        stage_id=parsed_stage_id,
        status=parsed_status,
    )
    return CommandResponse.from_model(cmd)


@router.get("/api/commands/{command_id}", response_model=CommandResponse)
def get_command(
    command_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> CommandResponse:
    service = _service(conn)
    cmd = service.get(command_id)
    if cmd is None:
        raise NotFoundError("Command not found")
    return CommandResponse.from_model(cmd)


@router.patch("/api/commands/{command_id}", response_model=CommandResponse)
def update_command(
    command_id: int,
    payload: CommandUpdateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> CommandResponse:
    parsed_stage_id = None
    if payload.stage_id is not None:
        parsed_stage_id = StageId.from_str(payload.stage_id)
        if parsed_stage_id is None:
            raise ValidationError("Invalid stage_id")

    parsed_status = None
    if payload.status is not None:
        parsed_status = Status.from_str(payload.status)
        if parsed_status is None:
            raise ValidationError("Invalid status")

    service = _service(conn)
    cmd = service.update(
        command_id,
        title=payload.title,
        stage_id=parsed_stage_id,
        status=parsed_status,
    )
    if cmd is None:
        raise NotFoundError("Command not found")
    return CommandResponse.from_model(cmd)


@router.delete("/api/commands/{command_id}")
def delete_command(
    command_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    service = _service(conn)
    ok = service.delete(command_id)
    if not ok:
        raise NotFoundError("Command not found")
    return {"ok": True}


@router.post("/api/commands/reorder")
def reorder_commands(
    payload: CommandReorderRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    """Persist a new ordering for one or more categories.

    The payload provides ordered command id lists keyed by category name.
    """

    by_stage_id: dict[StageId, list[int]] = {}
    for raw_stage_id, ids in payload.by_stage_id.items():
        parsed = StageId.from_str(raw_stage_id)
        if parsed is None:
            raise ValidationError("Invalid stage_id")
        by_stage_id[parsed] = ids

    service = _service(conn)
    service.reorder(by_stage_id)
    return {"ok": True}
