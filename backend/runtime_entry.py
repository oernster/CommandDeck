from __future__ import annotations

"""Packaged runtime entrypoint for CommandDeck.exe.

DEV/runtime expectations from README are preserved:
- backend server is on http://127.0.0.1:8001
- frontend production build is served by the backend on the same address

Deviation for packaging (required):
- In frozen mode, we start uvicorn in-process (no external python required).
"""

import os
import shutil
import sys
import threading
import time
import webbrowser
import traceback
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Command Deck"
APP_ID = "CommandDeck"
HOST = "127.0.0.1"
PORT = 8001
UI_URL = f"http://{HOST}:{PORT}/"


def _is_frozen_runtime() -> bool:
    """Return True when running as the packaged Windows runtime."""

    try:
        if getattr(sys, "frozen", False):
            return True
    except Exception:
        pass

    try:
        return str(sys.argv[0]).lower().endswith(".exe")
    except Exception:
        return False


def _exe_dir() -> Path:
    try:
        return Path(sys.argv[0]).resolve().parent
    except Exception:
        return Path.cwd()


def _runtime_log_path() -> Path:
    return _exe_dir() / "CommandDeck-runtime.log"


def _find_embedded_frontend_dist_dir() -> Path | None:
    """Locate `frontend/dist` inside the extracted onefile runtime.

    For Nuitka onefile builds, bundled data files are extracted into a temporary
    directory at process start. `sys.argv[0]` points at the installed EXE, but
    the bundled data lives near this module's extracted location.

    We find the extracted runtime root by walking up from `__file__` and looking
    for `frontend/dist/index.html`.
    """

    try:
        here = Path(__file__).resolve()
    except Exception:
        return None

    for parent in [here.parent, *here.parents]:
        candidate = parent / "frontend" / "dist" / "index.html"
        if candidate.is_file():
            return candidate.parent
    return None


def _copy_tree(src_dir: Path, dst_dir: Path) -> None:
    """Copy directory tree from src to dst (overwriting files)."""

    dst_dir.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src_dir):
        root_path = Path(root)
        rel = root_path.relative_to(src_dir)
        out_root = dst_dir / rel
        out_root.mkdir(parents=True, exist_ok=True)
        for d in dirs:
            (out_root / d).mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(root_path / f, out_root / f)


def _ensure_frontend_dist_present() -> None:
    """Best-effort self-heal for missing frontend/dist.

    In some deployments the installer payload may fail to copy `frontend/dist`.
    We also embed `frontend/dist` into the runtime onefile so we can restore it
    on first run.
    """

    try:
        # Only self-heal in packaged installs. In dev/test runs this module may
        # execute from source, and we must not write into the repo tree.
        if not _is_frozen_runtime():
            return

        install_dist_dir = _exe_dir() / "frontend" / "dist"
        install_index = install_dist_dir / "index.html"
        if install_index.is_file():
            _debug_log(f"[runtime] frontend/dist present at {install_dist_dir}")
            return

        embedded_dist_dir = _find_embedded_frontend_dist_dir()
        if embedded_dist_dir is None:
            _debug_log("[runtime] frontend/dist missing and no embedded dist found")
            return

        embedded_index = embedded_dist_dir / "index.html"
        if not embedded_index.is_file():
            _debug_log("[runtime] embedded dist dir found but index.html missing")
            return

        _debug_log(
            "[runtime] Restoring frontend/dist from embedded resources: "
            f"{embedded_dist_dir} -> {install_dist_dir}"
        )
        _copy_tree(embedded_dist_dir, install_dist_dir)
        if install_index.is_file():
            _debug_log(f"[runtime] frontend/dist restored to {install_dist_dir}")
    except Exception:
        # Never prevent startup due to UI assets; the backend can still run.
        return


def _debug_log(message: str) -> None:
    try:
        with _runtime_log_path().open("a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def _debug_log_exception(prefix: str, exc: BaseException) -> None:
    _debug_log(f"{prefix}: {exc!r}")
    try:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _debug_log(tb)
    except Exception:
        pass


def _show_fatal_error(message: str) -> None:
    """Best-effort GUI message for non-background launches on Windows."""

    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message, APP_NAME, 0x10)  # MB_ICONERROR
    except Exception:
        return


def _ensure_backend_imports() -> None:
    """Ensure `app.*` is importable when the EXE runs from an install directory."""
    # Prefer the packaged modules inside CommandDeck.exe when frozen.
    # Only fall back to an adjacent backend/ directory if imports fail.
    try:
        import app.main  # noqa: F401

        return
    except Exception:
        pass

    # Installed payload layout: <install_dir>/backend/app/*
    backend_dir = _exe_dir() / "backend"
    if backend_dir.is_dir():
        sys.path.insert(0, str(backend_dir))
        return

    # Source layout: this file is backend/runtime_entry.py
    try:
        here_backend = Path(__file__).resolve().parent
        sys.path.insert(0, str(here_backend))
    except Exception:
        pass


class _SingleInstanceLock:
    def __init__(self) -> None:
        self._fh = None

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True

        try:
            import msvcrt  # type: ignore
        except Exception:
            return True

        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home())
        lock_dir = Path(local_appdata) / APP_ID
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / "commanddeck.lock"

        try:
            fh = open(lock_path, "a+")  # noqa: PTH123
            self._fh = fh
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except Exception:
            try:
                if self._fh:
                    self._fh.close()
            except Exception:
                pass
            self._fh = None
            return False


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    host: str = HOST
    port: int = PORT

    @property
    def url(self) -> str:
        # The packaged runtime serves the production frontend build from the
        # backend on the same address (see README). The Vite dev-server port
        # (typically 5173) is for development only.
        return UI_URL


class BackendServer:
    def __init__(self) -> None:
        self._server = None
        self._thread: threading.Thread | None = None

    def start(self, *, host: str, port: int) -> None:
        try:
            import uvicorn

            _ensure_backend_imports()
            from app.main import app as fastapi_app
        except Exception as exc:  # noqa: BLE001
            _debug_log_exception("[runtime] Failed to import backend modules", exc)
            raise

        # Uvicorn's default logging config uses a formatter that calls
        # `sys.stderr.isatty()`. In --windows-console-mode=disable builds,
        # `sys.stderr` can be None, causing startup to crash.
        #
        # We disable uvicorn's logging configuration entirely (we already log
        # fatal errors to CommandDeck-runtime.log).
        config = uvicorn.Config(
            app=fastapi_app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        server = uvicorn.Server(config)
        self._server = server

        def _run() -> None:
            _debug_log("[runtime] uvicorn server thread starting")
            try:
                server.run()
            except Exception as exc:  # noqa: BLE001
                _debug_log(f"[runtime] uvicorn server crashed: {exc!r}")

        t = threading.Thread(target=_run, name="uvicorn-thread", daemon=True)
        self._thread = t
        t.start()

    def stop(self) -> None:
        server = self._server
        if server is not None:
            server.should_exit = True


def _load_tray_icon() -> object:
    """Load tray icon from CommandDeck.ico, falling back to a simple square."""
    try:
        from PIL import Image

        ico_candidates = [
            _exe_dir() / f"{APP_ID}.ico",
            _exe_dir() / "CommandDeck.ico",
        ]
        for p in ico_candidates:
            if p.is_file():
                return Image.open(p)
    except Exception:
        pass

    # Fallback: deterministic placeholder.
    try:
        from PIL import Image

        image = Image.new("RGBA", (64, 64), (20, 22, 28, 255))
        inset = Image.new("RGBA", (44, 44), (134, 59, 255, 255))
        image.paste(inset, (10, 10))
        return image
    except Exception:
        return object()


def _run_tray(
    *, settings: RuntimeSettings, backend: BackendServer, no_browser: bool
) -> int:
    try:
        import pystray
    except Exception as exc:  # noqa: BLE001
        _debug_log_exception("[runtime] Failed to import pystray", exc)
        raise

    def _open(_: object, __: object) -> None:
        webbrowser.open(settings.url)

    def _quit(icon: object, __: object) -> None:
        backend.stop()
        icon_stop = getattr(icon, "stop", None)
        if callable(icon_stop):
            icon_stop()

    icon = pystray.Icon(
        "command-deck",
        _load_tray_icon(),
        APP_NAME,
        pystray.Menu(
            pystray.MenuItem("Open Command Deck", _open, default=True),
            pystray.MenuItem("Quit", _quit),
        ),
    )

    # When launched interactively (Start Menu/Desktop), open the web UI.
    # When launched in the background (auto-start), `--no-browser` suppresses it.
    if not no_browser:
        try:
            webbrowser.open(settings.url)
        except Exception as exc:  # noqa: BLE001
            _debug_log_exception("[runtime] Failed to open browser", exc)

    icon.run()
    return 0


def main() -> int:
    _debug_log("[runtime] main() starting")
    no_browser = "--no-browser" in sys.argv or "--background" in sys.argv

    # In Windows GUI (no-console) mode, stdio handles can be None.
    # Ensure they're usable for libraries that expect `.isatty()`.
    try:
        if sys.stdout is None or not hasattr(sys.stdout, "isatty"):
            sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: PTH123
        if sys.stderr is None or not hasattr(sys.stderr, "isatty"):
            sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: PTH123
    except Exception:
        pass

    try:
        lock = _SingleInstanceLock()
        if not lock.acquire():
            _debug_log("[runtime] Another instance already running")
            if not no_browser:
                try:
                    webbrowser.open(f"http://{HOST}:{PORT}/")
                except Exception:
                    pass
            return 0

        _ensure_frontend_dist_present()
        settings = RuntimeSettings()
        backend = BackendServer()
        _debug_log(f"[runtime] Starting backend on {settings.url}")
        backend.start(host=settings.host, port=settings.port)

        # Minimal delay; keep dependency-free. Uvicorn comes up quickly.
        deadline = time.time() + 3.0
        while time.time() < deadline:
            time.sleep(0.05)

        _debug_log("[runtime] Starting tray")
        return _run_tray(settings=settings, backend=backend, no_browser=no_browser)
    except Exception as exc:  # noqa: BLE001
        _debug_log_exception("[runtime] Fatal error", exc)
        if not no_browser:
            _show_fatal_error(
                f"{APP_NAME} failed to start.\n\n"
                f"Details were written to:\n{_runtime_log_path()}"
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
