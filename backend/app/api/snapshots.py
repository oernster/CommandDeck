from __future__ import annotations

import sqlite3
from typing import cast

from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.domain.models import epoch_seconds_to_iso8601_z
from app.domain.schemas import SnapshotLoadResponse, SnapshotSummary
from app.repositories.board_repository import BoardRepository
from app.repositories.snapshot_repository import SnapshotRepository
from app.services.snapshot_service import SnapshotService

router = APIRouter()


def _service(conn: sqlite3.Connection) -> SnapshotService:
    return SnapshotService(
        conn=conn,
        board=BoardRepository(conn),
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
def save_snapshot(conn: sqlite3.Connection = Depends(get_db)) -> SnapshotSummary:
    service = _service(conn)
    out = service.save_now()
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

