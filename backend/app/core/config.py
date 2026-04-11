from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    v1 keeps configuration deliberately minimal.
    """

    host: str = "127.0.0.1"
    port: int = 8001
    sqlite_path: str = "command_deck.db"


SETTINGS = Settings()
