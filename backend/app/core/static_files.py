from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.staticfiles import StaticFiles


def _runtime_root_dir() -> Path:
    """Return the runtime root directory.

    - In packaged/frozen installs, the EXE lives in the install directory; we
      treat that as the runtime root.
    - In dev/source, preserve the existing repo-root derived path.
    """
    try:
        if getattr(__import__("sys"), "frozen", False):
            return Path(__import__("sys").argv[0]).resolve().parent
    except Exception:
        pass

    backend_dir = Path(__file__).resolve().parents[2]
    return backend_dir.parent


def frontend_dist_dir() -> Path:
    """Return the expected path to the frontend production build.

    We keep this as a small helper so `app.main` doesn't hardcode relative paths.

    If `COMMANDDECK_FRONTEND_DIST_DIR` is set, it overrides the default location.
    This is mainly useful for tests and non-standard deployments.
    """

    override = os.environ.get("COMMANDDECK_FRONTEND_DIST_DIR")
    if override:
        return Path(override).expanduser().resolve()

    # Preferred: installed payload uses: <install_root>/frontend/dist
    try:
        exe_root = Path(sys.argv[0]).resolve().parent
        installed = exe_root / "frontend" / "dist"
        if (installed / "index.html").is_file():
            return installed
    except Exception:
        pass

    # Fallback: in onefile mode, data dirs are extracted next to the executing
    # Python files under a temporary extraction root. Search upwards from this
    # module for a sibling frontend/dist.
    try:
        here = Path(__file__).resolve()
        for parent in list(here.parents)[:8]:
            candidate = parent / "frontend" / "dist"
            if (candidate / "index.html").is_file():
                return candidate
    except Exception:
        pass

    # Default guess (may not exist).
    root = _runtime_root_dir()
    return root / "frontend" / "dist"


class AssetsStaticFiles(StaticFiles):
    """Static file handler for Vite hashed build assets.

    Vite emits content-hashed filenames under `/assets/*`. Those responses are
    immutable and safe to cache for a long time.

    We set the header here (at the static-serving boundary) instead of using a
    global middleware so non-asset routes keep their default caching behavior.
    """

    _CACHE_CONTROL_VALUE = "public, max-age=31536000, immutable"

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        # Override any default Cache-Control set by Starlette.
        #
        # Note: for missing assets, Starlette raises an HTTPException instead of
        # returning a Response, so this line only applies to successful responses.
        response.headers["Cache-Control"] = self._CACHE_CONTROL_VALUE
        return response
