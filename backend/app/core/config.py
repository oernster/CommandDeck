from __future__ import annotations

from dataclasses import dataclass, field
import os
import sys


def _repo_root() -> str:
    # backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> repo
    here = __file__
    core_dir = __import__("os").path.dirname(__import__("os").path.abspath(here))
    app_dir = __import__("os").path.dirname(core_dir)
    backend_dir = __import__("os").path.dirname(app_dir)
    repo_root = __import__("os").path.dirname(backend_dir)
    return repo_root


def _runtime_root() -> str:
    """Resolve the directory that should be treated as the runtime root.

    In source/dev/test, this is the repo root.
    In frozen/runtime installs, this is the directory containing the EXE.
    """
    try:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        pass
    return _repo_root()


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    v1 keeps configuration deliberately minimal.
    """

    host: str = "127.0.0.1"
    port: int = 8001
    # Use an explicit repo-rooted path so tests and app runtime agree regardless
    # of current working directory.
    sqlite_path: str = field(
        default_factory=lambda: os.path.join(_runtime_root(), "command_deck.db")
    )


SETTINGS = Settings()
