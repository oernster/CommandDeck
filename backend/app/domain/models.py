from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.enums import Category, Status


def utc_now_epoch_seconds() -> int:
    return int(datetime.now(tz=UTC).timestamp())


def epoch_seconds_to_iso8601_z(epoch_seconds: int) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, tz=UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True, slots=True)
class Command:
    id: int
    title: str
    category: Category
    status: Status
    created_at: int  # UTC epoch seconds


@dataclass(frozen=True, slots=True)
class Outcome:
    id: int
    command_id: int
    note: str
    created_at: int  # UTC epoch seconds


@dataclass(frozen=True, slots=True)
class Session:
    id: int
    category: Category
    started_at: int  # UTC epoch seconds
    ended_at: int | None  # UTC epoch seconds
