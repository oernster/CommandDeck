from __future__ import annotations

from pydantic import BaseModel, Field
from app.domain.models import Command, Outcome, Session, epoch_seconds_to_iso8601_z


class CommandCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    category: str
    status: str | None = None


class CommandUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    category: str | None = None
    status: str | None = None


class CommandReorderRequest(BaseModel):
    """Reorder commands within (and optionally across) categories.

    The payload provides the *full ordered list* of command ids for each category
    affected by the move. This makes the operation deterministic and easy to
    validate.
    """

    by_category: dict[str, list[int]]


class CommandResponse(BaseModel):
    id: int
    title: str
    category: str
    status: str
    created_at: str

    @classmethod
    def from_model(cls, cmd: Command) -> "CommandResponse":
        return cls(
            id=cmd.id,
            title=cmd.title,
            category=cmd.category.value,
            status=cmd.status.value,
            created_at=epoch_seconds_to_iso8601_z(cmd.created_at),
        )


class OutcomeCreateRequest(BaseModel):
    note: str = Field(min_length=1)


class OutcomeResponse(BaseModel):
    id: int
    command_id: int
    note: str
    created_at: str

    @classmethod
    def from_model(cls, outcome: Outcome) -> "OutcomeResponse":
        return cls(
            id=outcome.id,
            command_id=outcome.command_id,
            note=outcome.note,
            created_at=epoch_seconds_to_iso8601_z(outcome.created_at),
        )


class SessionStartRequest(BaseModel):
    category: str = Field(min_length=1)


class SessionResponse(BaseModel):
    id: int
    category: str
    started_at: str
    ended_at: str | None

    @classmethod
    def from_model(cls, session: Session) -> "SessionResponse":
        return cls(
            id=session.id,
            category=session.category.value,
            started_at=epoch_seconds_to_iso8601_z(session.started_at),
            ended_at=(
                epoch_seconds_to_iso8601_z(session.ended_at)
                if session.ended_at is not None
                else None
            ),
        )


# Keyed by category name ("Design", "Build", ...). Value is the latest session
# for that category, or null if no session has ever been recorded.
SessionLatestByCategory = dict[str, SessionResponse | None]
