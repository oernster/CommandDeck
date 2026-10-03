"""The Command Deck version, read from the repository-root VERSION file.

VERSION is the single source of truth; this module never carries its own copy.
The backend uses it for the FastAPI app metadata.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

VERSION_FILENAME = "VERSION"
FALLBACK_VERSION = "0.0.0-dev"


def _candidate_paths() -> list[Path]:
    """Where VERSION sits relative to this module, in every layout it runs in.

    The packaged runtime extracts `app/` with VERSION beside it, so the file is
    one level up. A source checkout and an installed copy both hold
    `<root>/backend/app/`, so the file is two levels up.
    """
    app_dir = Path(__file__).resolve().parent
    return [app_dir.parent / VERSION_FILENAME, app_dir.parents[1] / VERSION_FILENAME]


def read_version(paths: Iterable[Path] | None = None) -> str:
    """Return the first non-empty VERSION found, else the dev fallback."""
    for path in _candidate_paths() if paths is None else paths:
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            return text
    return FALLBACK_VERSION


VERSION = read_version()
