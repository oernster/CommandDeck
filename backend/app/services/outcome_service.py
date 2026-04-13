from __future__ import annotations

from collections.abc import Callable

from app.domain.errors import NotFoundError, ValidationError
from app.domain.models import Outcome, utc_now_epoch_seconds
from app.repositories.command_repository import CommandRepository
from app.repositories.outcome_repository import OutcomeRepository


class OutcomeService:
    def __init__(
        self,
        *,
        outcomes: OutcomeRepository,
        commands: CommandRepository,
        now_epoch_seconds: Callable[[], int] = utc_now_epoch_seconds,
    ) -> None:
        self._outcomes = outcomes
        self._commands = commands
        self._now_epoch_seconds = now_epoch_seconds

    def list_for_command(self, command_id: int) -> list[Outcome]:
        if self._commands.get(command_id) is None:
            raise NotFoundError("Command not found")
        return self._outcomes.list_for_command(command_id)

    def latest_and_counts_for_commands(
        self, command_ids: list[int]
    ) -> tuple[dict[int, Outcome], dict[int, int]]:
        # Intentionally does not validate existence of each command id; the
        # caller may send ids that were just deleted or are out-of-scope.
        return self._outcomes.latest_and_counts_for_commands(command_ids)

    def list_for_commands(self, command_ids: list[int]) -> dict[int, list[Outcome]]:
        # Intentionally does not validate existence of each command id; the caller
        # may send ids that were just deleted or are out-of-scope.
        return self._outcomes.list_for_commands(command_ids)

    def create(self, *, command_id: int, note: str) -> Outcome:
        if self._commands.get(command_id) is None:
            raise NotFoundError("Command not found")
        if note.strip() == "":
            raise ValidationError("Note must not be empty")

        created_at = int(self._now_epoch_seconds())
        return self._outcomes.create(
            command_id=command_id,
            note=note.strip(),
            created_at=created_at,
        )

    def delete(self, outcome_id: int) -> bool:
        return self._outcomes.delete(outcome_id)
