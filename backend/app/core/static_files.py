from __future__ import annotations

import os
from pathlib import Path


def frontend_dist_dir() -> Path:
    """Return the expected path to the frontend production build.

    We keep this as a small helper so `app.main` doesn't hardcode relative paths.

    If `COMMANDDECK_FRONTEND_DIST_DIR` is set, it overrides the default location.
    This is mainly useful for tests and non-standard deployments.
    """

    override = os.environ.get("COMMANDDECK_FRONTEND_DIST_DIR")
    if override:
        return Path(override).expanduser().resolve()

    # backend/app/core/static_files.py -> backend/app/core -> backend/app -> backend
    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    return repo_root / "frontend" / "dist"
