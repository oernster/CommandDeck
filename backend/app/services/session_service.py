from __future__ import annotations

from collections.abc import Callable

from app.domain.enums import Category
from app.domain.models import Session, utc_now_epoch_seconds
from app.repositories.session_repository import SessionRepository


class SessionService:
    def __init__(
        self,
        repo: SessionRepository,
        *,
        now_epoch_seconds: Callable[[], int] = utc_now_epoch_seconds,
    ) -> None:
        self._repo = repo
        self._now_epoch_seconds = now_epoch_seconds

    def list(
        self, *, category: Category | None = None, active: bool | None = None
    ) -> list[Session]:
        return self._repo.list(category=category, active=active)

    def get_active(self) -> Session | None:
        return self._repo.get_active()

    def start(self, *, category: Category) -> Session:
        now = int(self._now_epoch_seconds())
        return self._repo.start(category=category, now_epoch_seconds=now)

    def stop(self) -> Session | None:
        now = int(self._now_epoch_seconds())
        return self._repo.stop(now_epoch_seconds=now)

    def latest_by_category(self) -> dict[Category, Session]:
        latest = self._repo.latest_by_category()
        return {s.category: s for s in latest}
