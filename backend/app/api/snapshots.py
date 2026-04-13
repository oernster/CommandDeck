from __future__ import annotations

import sqlite3
from typing import cast

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.errors import NotFoundError, ValidationError
from app.domain.models import epoch_seconds_to_iso8601_z
from app.domain.schemas import (
    SnapshotLoadResponse,
    SnapshotRenameRequest,
    SnapshotSaveRequest,
    SnapshotSummary,
)
from app.repositories.board_repository import BoardRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.snapshot_service import SnapshotService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> SnapshotService:
    return SnapshotService(
        conn=conn,
        board=BoardRepository(conn),
        sessions=SessionRepository(conn),
        snapshots=SnapshotRepository(conn),
    )


@router.get("/api/snapshots", response_model=list[SnapshotSummary])
def list_snapshots(conn: sqlite3.Connection = Depends(get_db)) -> list[SnapshotSummary]:
    service = _service(conn)
    items = service.list()
    return [
        SnapshotSummary(
            id=cast(int, s["id"]),
            name=cast(str, s["name"]),
            saved_at=epoch_seconds_to_iso8601_z(cast(int, s["saved_at"])),
        )
        for s in items
    ]


@router.post("/api/snapshots", response_model=SnapshotSummary, status_code=201)
def save_snapshot(
    payload: SnapshotSaveRequest | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> SnapshotSummary:
    service = _service(conn)
    name = payload.name if payload is not None else None
    out = service.save_now(name=name)
    return SnapshotSummary(
        id=cast(int, out["id"]),
        name=cast(str, out["name"]),
        saved_at=epoch_seconds_to_iso8601_z(cast(int, out["saved_at"])),
    )


@router.post("/api/snapshots/{snapshot_id}/load", response_model=SnapshotLoadResponse)
def load_snapshot(
    snapshot_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> SnapshotLoadResponse:
    service = _service(conn)
    service.load(snapshot_id=snapshot_id)
    return SnapshotLoadResponse(ok=True)


@router.patch("/api/snapshots/{snapshot_id}", response_model=SnapshotSummary)
def rename_snapshot(
    snapshot_id: int,
    payload: SnapshotRenameRequest,
    conn: sqlite3.Connection = Depends(get_db),
) -> SnapshotSummary:
    cleaned = payload.name.strip()
    if not cleaned:
        raise ValidationError("Name must not be empty")

    repo = SnapshotRepository(conn)
    if not repo.exists(snapshot_id):
        raise NotFoundError("Snapshot not found")

    repo.update_name(snapshot_id=snapshot_id, name=cleaned)
    row = repo.get_summary(snapshot_id)
    assert row is not None
    return SnapshotSummary(
        id=cast(int, row["id"]),
        name=cast(str, row["name"]),
        saved_at=epoch_seconds_to_iso8601_z(cast(int, row["saved_at"])),
    )


@router.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(
    snapshot_id: int,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    service = _service(conn)
    service.delete(snapshot_id=snapshot_id)
    return {"ok": True}

