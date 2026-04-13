from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.errors import NotFoundError
from app.domain.schemas import (
    OutcomeCreateRequest,
    OutcomeResponse,
    OutcomesLatestRequest,
    OutcomesLatestResponse,
)
from app.repositories.command_repository import CommandRepository
from app.repositories.outcome_repository import OutcomeRepository
from app.services.outcome_service import OutcomeService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> OutcomeService:
    return OutcomeService(
        outcomes=OutcomeRepository(conn),
        commands=CommandRepository(conn),
    )


@router.get(
    "/api/commands/{command_id}/outcomes",
    response_model=list[OutcomeResponse],
)
def list_outcomes(
    command_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> list[OutcomeResponse]:
    service = _service(conn)
    return [OutcomeResponse.from_model(o) for o in service.list_for_command(command_id)]


@router.post(
    "/api/commands/{command_id}/outcomes",
    response_model=OutcomeResponse,
    status_code=201,
)
def create_outcome(
    command_id: int,
    payload: OutcomeCreateRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> OutcomeResponse:
    service = _service(conn)
    out = service.create(command_id=command_id, note=payload.note)
    return OutcomeResponse.from_model(out)


@router.post(
    "/api/outcomes/latest",
    response_model=OutcomesLatestResponse,
)
def latest_outcomes(
    payload: OutcomesLatestRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> OutcomesLatestResponse:
    service = _service(conn)
    latest, counts = service.latest_and_counts_for_commands(payload.command_ids)
    return OutcomesLatestResponse(
        by_command_id={
            cid: OutcomeResponse.from_model(out) for cid, out in latest.items()
        },
        counts_by_command_id=counts,
    )


@router.delete("/api/outcomes/{outcome_id}")
def delete_outcome(
    outcome_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    service = _service(conn)
    ok = service.delete(outcome_id)
    if not ok:
        raise NotFoundError("Outcome not found")
    return {"ok": True}
