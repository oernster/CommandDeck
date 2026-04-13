from __future__ import annotations

from collections.abc import Callable

from app.domain.enums import StageId, Status
from app.domain.errors import ValidationError
from app.domain.models import Command, utc_now_epoch_seconds
from app.repositories.command_repository import CommandRepository


class CommandService:
    def __init__(
        self,
        repo: CommandRepository,
        *,
        now_epoch_seconds: Callable[[], int] = utc_now_epoch_seconds,
    ) -> None:
        self._repo = repo
        self._now_epoch_seconds = now_epoch_seconds

    def list(
        self, stage_id: StageId | None = None, status: Status | None = None
    ) -> list[Command]:
        return self._repo.list(stage_id=stage_id, status=status)

    def create(self, title: str, stage_id: StageId, status: Status) -> Command:
        if title.strip() == "":
            raise ValidationError("Title must not be empty")
        created_at = int(self._now_epoch_seconds())
        return self._repo.create(
            title=title.strip(),
            stage_id=stage_id,
            status=status,
            created_at=created_at,
        )

    def get(self, command_id: int) -> Command | None:
        return self._repo.get(command_id)

    def update(
        self,
        command_id: int,
        title: str | None,
        stage_id: StageId | None,
        status: Status | None,
    ) -> Command | None:
        if title is not None and title.strip() == "":
            raise ValidationError("Title must not be empty")
        stripped = title.strip() if title is not None else None
        return self._repo.update(
            command_id=command_id,
            title=stripped,
            stage_id=stage_id,
            status=status,
        )

    def delete(self, command_id: int) -> bool:
        return self._repo.delete(command_id)

    def reorder(self, by_stage_id: dict[StageId, list[int]]) -> None:
        # Basic validation - full coverage per stage is enforced in the repo.
        for stage_id, ids in by_stage_id.items():
            if not ids:
                # Allow empty payload only if category truly has no commands,
                # which will be verified against the DB.
                continue
            if len(ids) != len(set(ids)):
                raise ValidationError(
                    f"Duplicate command id in {stage_id.value} ordering"
                )

        try:
            self._repo.reorder(by_stage_id)
        except ValueError as e:
            raise ValidationError(str(e)) from e
