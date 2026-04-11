from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from typing import Callable, Protocol, cast

from app.core.config import SETTINGS


@dataclass(frozen=True, slots=True)
class TraySettings:
    host: str = SETTINGS.host
    port: int = SETTINGS.port

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"


class BackendProcess:
    def __init__(self, proc: subprocess.Popen[str]) -> None:
        self._proc = proc

    def is_running(self) -> bool:
        return self._proc.poll() is None

    def stop(self) -> None:
        if self.is_running():
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)


def _repo_root() -> str:
    # backend/app/tray/runtime.py -> backend/app/tray -> backend/app -> backend -> repo
    here = os.path.abspath(__file__)
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(here)))
    repo_root = os.path.dirname(backend_dir)
    return repo_root


def _venv_python_exe(repo_root: str) -> str:
    return os.path.join(repo_root, "venv", "Scripts", "python.exe")


def _backend_workdir(repo_root: str) -> str:
    return os.path.join(repo_root, "backend")


def _start_backend(settings: TraySettings) -> BackendProcess:
    return _start_backend_with_popen(settings=settings, popen_factory=subprocess.Popen)


def _start_backend_with_popen(
    *,
    settings: TraySettings,
    popen_factory: Callable[..., subprocess.Popen[str]],
) -> BackendProcess:
    repo_root = _repo_root()
    python_exe = _venv_python_exe(repo_root)
    backend_cwd = _backend_workdir(repo_root)

    if not os.path.isfile(python_exe):
        # Be resilient in dev/test environments where the repo may not ship
        # with a local venv folder. Fall back to the current interpreter.
        python_exe = sys.executable
        if not python_exe or not os.path.isfile(python_exe):
            raise RuntimeError(
                "Could not find a usable Python executable. "
                "Expected venv/Scripts/python.exe or a valid sys.executable."
            )

    env = dict(os.environ)
    # Ensure static frontend serving works when frontend has been built.
    env.pop("COMMANDDECK_FRONTEND_DIST_DIR", None)

    args = [
        python_exe,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        settings.host,
        "--port",
        str(settings.port),
    ]

    proc = popen_factory(
        args,
        cwd=backend_cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return BackendProcess(proc)


def _wait_until_up(url: str, timeout_seconds: float = 3.0) -> None:
    # Minimal "good enough" delay. Keep simple and deterministic; no polling dependency.
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        time.sleep(0.05)


def _build_icon() -> object:
    """Build the tray icon image.

    Extracted for testability/coverage; keeps icon creation deterministic.
    """
    from PIL import Image

    image = Image.new("RGBA", (64, 64), (20, 22, 28, 255))
    inset = Image.new("RGBA", (44, 44), (120, 170, 255, 255))
    image.paste(inset, (10, 10))
    return image


class TrayIcon(Protocol):
    def run(self) -> None: ...

    def stop(self) -> None: ...


def _default_icon_factory(
    *,
    on_open: Callable[[], None],
    on_quit: Callable[[], None],
    title: str,
) -> TrayIcon:
    # Imported lazily so tests can cover tray logic without requiring GUI integration.
    import pystray

    def _open(_: object, __: object) -> None:
        on_open()

    def _quit(icon: object, __: object) -> None:
        on_quit()
        # Avoid importing pystray types at module import time.
        icon_stop = getattr(icon, "stop", None)
        if callable(icon_stop):
            icon_stop()

    image = _build_icon()

    menu = pystray.Menu(
        pystray.MenuItem("Open Command Deck", _open, default=True),
        pystray.MenuItem("Quit", _quit),
    )

    return cast(TrayIcon, pystray.Icon("command-deck", image, title, menu))


def run_tray(
    *,
    platform: str | None = None,
    start_backend: Callable[[TraySettings], BackendProcess] = _start_backend,
    open_browser: Callable[[str], object] = webbrowser.open,
    wait_until_up: Callable[[str], None] = _wait_until_up,
    icon_factory: Callable[..., TrayIcon] = _default_icon_factory,
) -> None:
    actual_platform = platform if platform is not None else sys.platform
    if actual_platform != "win32":
        raise RuntimeError("Tray runtime is Windows-only in v1")

    settings = TraySettings()
    backend = start_backend(settings)

    # In practice, uvicorn comes up quickly; keep simple.
    wait_until_up(settings.url)

    def on_open() -> None:
        open_browser(settings.url)

    def on_quit() -> None:
        backend.stop()

    icon = icon_factory(on_open=on_open, on_quit=on_quit, title="Command Deck")
    icon.run()
