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
    # Prefer detecting the actual CommandDeck.exe path even when the process is
    # not marked as frozen (some packaging/launch contexts can misreport it).
    try:
        argv0 = str(sys.argv[0]) if sys.argv else ""
        exe_name = os.path.basename(argv0).lower()
        if exe_name == "commanddeck.exe":
            return os.path.dirname(os.path.abspath(argv0))
    except Exception:
        # Fall through to frozen / repo-root logic.
        pass

    try:
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        pass

    return _repo_root()


def _default_sqlite_path() -> str:
    """Default SQLite DB path.

    Goals:
    - Installed/runtime (frozen / exe): keep DB next to the EXE (install dir).
    - Source/dev: never write DB files into the repository tree; use a per-user
      app data directory instead.

    `COMMANDDECK_SQLITE_PATH` can override this if needed.
    """

    override = os.environ.get("COMMANDDECK_SQLITE_PATH")
    if override:
        return os.path.abspath(os.path.expanduser(override))

    # Packaged runtime (or direct CommandDeck.exe run): store next to the executable.
    try:
        argv0 = str(sys.argv[0]) if sys.argv else ""
        exe_name = os.path.basename(argv0).lower()
        is_frozen = bool(getattr(sys, "frozen", False))
        # Do not require the file to exist: tests and some launch contexts may
        # provide an argv0 that points at the intended EXE path before it exists
        # (or in a synthetic environment).
        is_runtime_exe = exe_name == "commanddeck.exe"

        if is_frozen or is_runtime_exe:
            return os.path.join(_runtime_root(), "command_deck.db")
    except Exception:
        pass

    # Dev/source: store under a user data directory.
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return os.path.join(base, "CommandDeck", "command_deck.db")

    # Fallback for non-Windows / missing env: use home directory.
    home = os.path.expanduser("~")
    return os.path.join(home, ".commanddeck", "command_deck.db")


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
        default_factory=_default_sqlite_path
    )


SETTINGS = Settings()
