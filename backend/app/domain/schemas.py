from __future__ import annotations

from pydantic import BaseModel, Field
from app.domain.models import Command, Outcome, Session, epoch_seconds_to_iso8601_z


class CommandCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    stage_id: str
    status: str | None = None


class CommandUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    stage_id: str | None = None
    status: str | None = None


class CommandReorderRequest(BaseModel):
    """Reorder commands within (and optionally across) categories.

    The payload provides the *full ordered list* of command ids for each category
    affected by the move. This makes the operation deterministic and easy to
    validate.
    """

    by_stage_id: dict[str, list[int]]


class CommandResponse(BaseModel):
    id: int
    title: str
    stage_id: str
    status: str
    created_at: str

    @classmethod
    def from_model(cls, cmd: Command) -> "CommandResponse":
        return cls(
            id=cmd.id,
            title=cmd.title,
            stage_id=cmd.stage_id.value,
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
    command_id: int


class SessionResponse(BaseModel):
    id: int
    command_id: int
    stage_id: str
    started_at: str
    ended_at: str | None

    @classmethod
    def from_model(cls, session: Session) -> "SessionResponse":
        return cls(
            id=session.id,
            command_id=session.command_id,
            stage_id=session.stage_id.value,
            started_at=epoch_seconds_to_iso8601_z(session.started_at),
            ended_at=(
                epoch_seconds_to_iso8601_z(session.ended_at)
                if session.ended_at is not None
                else None
            ),
        )


class BoardResponse(BaseModel):
    name: str
    user_named: bool
    is_new_unnamed: bool
    stage_labels: dict[str, str] | None = None


class BoardUpdateRequest(BaseModel):
    name: str = Field(min_length=0)


class StageLabelsUpdateRequest(BaseModel):
    stage_labels: dict[str, str]


class SnapshotSummary(BaseModel):
    id: int
    name: str
    saved_at: str


class SnapshotLoadResponse(BaseModel):
    ok: bool = True


class SnapshotRenameRequest(BaseModel):
    name: str = Field(min_length=0)


# Keyed by stage id ("DESIGN", "BUILD", ...). Value is the latest session
# for that stage, or null if no session has ever been recorded.
SessionLatestByStageId = dict[str, SessionResponse | None]
