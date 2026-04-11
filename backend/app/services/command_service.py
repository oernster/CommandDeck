from __future__ import annotations

from collections.abc import Callable

from app.domain.enums import Category, Status
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
        self, category: Category | None = None, status: Status | None = None
    ) -> list[Command]:
        return self._repo.list(category=category, status=status)

    def create(self, title: str, category: Category, status: Status) -> Command:
        if title.strip() == "":
            raise ValidationError("Title must not be empty")
        created_at = int(self._now_epoch_seconds())
        return self._repo.create(
            title=title.strip(),
            category=category,
            status=status,
            created_at=created_at,
        )

    def get(self, command_id: int) -> Command | None:
        return self._repo.get(command_id)

    def update(
        self,
        command_id: int,
        title: str | None,
        category: Category | None,
        status: Status | None,
    ) -> Command | None:
        if title is not None and title.strip() == "":
            raise ValidationError("Title must not be empty")
        stripped = title.strip() if title is not None else None
        return self._repo.update(
            command_id=command_id,
            title=stripped,
            category=category,
            status=status,
        )

    def delete(self, command_id: int) -> bool:
        return self._repo.delete(command_id)
