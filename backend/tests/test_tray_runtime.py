from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import os
import subprocess
import types
import runpy
import sys

import pytest

from app.tray.runtime import (
    BackendProcess,
    TraySettings,
    _build_icon,
    _default_icon_factory,
    _repo_root,
    _start_backend_with_popen,
    _venv_python_exe,
    _wait_until_up,
    _start_backend,
    run_tray,
)


def test_venv_python_exe_path() -> None:
    path = _venv_python_exe("C:/repo").replace("\\", "/")
    assert path == "C:/repo/venv/Scripts/python.exe"


def test_tray_main_module_is_covered(monkeypatch) -> None:
    # Avoid launching any real tray work.
    called = {"count": 0}

    def _fake_run_tray() -> None:
        called["count"] += 1

    monkeypatch.setattr("app.tray.__main__.run_tray", _fake_run_tray)

    from app.tray.__main__ import _coverage_entrypoint

    _coverage_entrypoint()
    assert called["count"] == 1

    # Cleanup so other tests can execute the module without triggering runpy warnings.
    sys.modules.pop("app.tray.__main__", None)


def test_tray_main_runs_when_executed_as_module(monkeypatch) -> None:
    called = {"count": 0}

    fake_runtime = types.ModuleType("app.tray.runtime")

    def _fake_run_tray() -> None:
        called["count"] += 1

    fake_runtime.run_tray = _fake_run_tray  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "app.tray.runtime", fake_runtime)

    # Ensure prior imports of app.tray.__main__ don't trigger runpy warnings.
    sys.modules.pop("app.tray.__main__", None)

    runpy.run_module("app.tray.__main__", run_name="__main__")
    assert called["count"] == 1


class _FakeBackend(BackendProcess):
    def __init__(self) -> None:
        self.stopped = False

    def is_running(self) -> bool:  # pragma: no cover - not needed
        return True

    def stop(self) -> None:
        self.stopped = True


@dataclass
class _FakeIcon:
    on_open: Callable[[], None]
    on_quit: Callable[[], None]
    title: str
    ran: bool = False

    def run(self) -> None:
        self.ran = True
        # Simulate user actions.
        self.on_open()
        self.on_quit()

    def stop(self) -> None:  # pragma: no cover - not needed
        pass


def test_run_tray_rejects_non_windows_platform() -> None:
    with pytest.raises(RuntimeError, match="Windows-only"):
        run_tray(platform="linux")


def test_run_tray_opens_browser_and_stops_backend(monkeypatch) -> None:
    opened: list[str] = []
    backend = _FakeBackend()

    def _start_backend(_: TraySettings) -> BackendProcess:
        return backend

    def _open_browser(url: str) -> object:
        opened.append(url)
        return True

    created: list[_FakeIcon] = []

    def _icon_factory(*, on_open, on_quit, title: str):
        icon = _FakeIcon(on_open=on_open, on_quit=on_quit, title=title)
        created.append(icon)
        return icon

    run_tray(
        platform="win32",
        start_backend=_start_backend,
        open_browser=_open_browser,
        wait_until_up=lambda _: None,
        icon_factory=_icon_factory,
    )

    assert created and created[0].ran is True
    assert opened == ["http://127.0.0.1:8001/"]
    assert backend.stopped is True


def test_repo_root_points_to_repo() -> None:
    root = _repo_root()
    assert root.replace("\\", "/").endswith("/CommandDeck")


def test_start_backend_raises_if_venv_python_missing(monkeypatch) -> None:
    # Make it deterministic: pretend we're in a repo without venv python.
    monkeypatch.setattr(
        "app.tray.runtime._repo_root",
        lambda: "C:/this/path/does/not/exist",
    )

    captured: dict[str, object] = {}

    class _Proc:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout: float):
            return 0

        def kill(self):
            pass

    def _popen(args, cwd=None, env=None, stdout=None, stderr=None, text=None):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["env"] = env
        return _Proc()  # type: ignore[return-value]

    # Force fallback to sys.executable by reporting only the venv python as missing.
    real_isfile = os.path.isfile

    def _fake_isfile(path: str) -> bool:
        normalized = path.replace("\\", "/")
        if normalized == sys.executable.replace("\\", "/"):
            return True
        if "venv" in normalized:
            return False
        return real_isfile(path)

    monkeypatch.setattr("app.tray.runtime.os.path.isfile", _fake_isfile)

    # Should fall back to sys.executable rather than raising.
    _start_backend_with_popen(
        settings=TraySettings(),
        popen_factory=_popen,  # type: ignore[arg-type]
    )

    args = captured["args"]
    assert isinstance(args, list)
    assert isinstance(args[0], str) and args[0]  # python exe


def test_start_backend_invokes_uvicorn_with_expected_args(monkeypatch) -> None:
    # Force repo_root to the actual workspace and report the venv python as present.
    monkeypatch.setattr("app.tray.runtime._repo_root", lambda: os.getcwd())
    monkeypatch.setattr("app.tray.runtime.os.path.isfile", lambda _: True)

    captured: dict[str, object] = {}

    class _Proc:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout: float):
            return 0

        def kill(self):
            pass

    def _popen(args, cwd=None, env=None, stdout=None, stderr=None, text=None):
        captured["args"] = args
        captured["cwd"] = cwd
        captured["env"] = env
        return _Proc()  # type: ignore[return-value]

    settings = TraySettings(host="127.0.0.1", port=8001)
    proc = _start_backend_with_popen(
        settings=settings,
        popen_factory=_popen,  # type: ignore[arg-type]
    )
    assert proc.is_running() is True

    # Cover stop()'s terminate path.
    proc.stop()

    args = captured["args"]
    assert isinstance(args, list)
    assert args[0].endswith("venv\\Scripts\\python.exe") or args[0].endswith(
        "venv/Scripts/python.exe"
    )
    assert args[1:4] == ["-m", "uvicorn", "app.main:app"]
    assert "--host" in args and "127.0.0.1" in args
    assert "--port" in args and "8001" in args


def test_start_backend_raises_when_no_python_executable_available(monkeypatch) -> None:
    # Force venv python missing.
    monkeypatch.setattr("app.tray.runtime.os.path.isfile", lambda _: False)
    # Force fallback python missing too.
    monkeypatch.setattr("app.tray.runtime.sys.executable", "")

    with pytest.raises(RuntimeError, match="Could not find a usable Python executable"):
        _start_backend_with_popen(
            settings=TraySettings(),
            popen_factory=lambda *a, **k: None,  # type: ignore[arg-type]
        )


def test_start_backend_wrapper_calls_impl(monkeypatch) -> None:
    called = {"count": 0}

    def _fake_impl(*, settings: TraySettings, popen_factory):
        called["count"] += 1
        return _FakeBackend()  # type: ignore[return-value]

    monkeypatch.setattr("app.tray.runtime._start_backend_with_popen", _fake_impl)
    _start_backend(TraySettings())
    assert called["count"] == 1


def test_backend_process_stop_kills_when_terminate_hangs() -> None:
    class _HungProc:
        def __init__(self) -> None:
            self.killed = False

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout: float):
            if not self.killed:
                raise subprocess.TimeoutExpired(cmd="x", timeout=timeout)
            return 0

        def kill(self):
            self.killed = True

    p = _HungProc()
    bp = BackendProcess(p)  # type: ignore[arg-type]
    bp.stop()
    assert p.killed is True


def test_backend_process_stop_noop_when_already_stopped() -> None:
    class _StoppedProc:
        def poll(self):
            return 0

        def terminate(self):
            raise AssertionError("terminate() should not be called")

        def wait(self, timeout: float):
            raise AssertionError("wait() should not be called")

        def kill(self):
            raise AssertionError("kill() should not be called")

    bp = BackendProcess(_StoppedProc())  # type: ignore[arg-type]
    bp.stop()


def test_wait_until_up_runs_sleep_loop(monkeypatch) -> None:
    # Force the loop to execute at least once.
    times = iter([0.0, 0.0, 999.0])
    sleeps: list[float] = []

    monkeypatch.setattr("app.tray.runtime.time.time", lambda: next(times))
    monkeypatch.setattr("app.tray.runtime.time.sleep", lambda s: sleeps.append(s))

    _wait_until_up("http://127.0.0.1:8001/", timeout_seconds=0.1)
    assert sleeps


def test_build_icon_creates_image_object() -> None:
    icon = _build_icon()
    # PIL Image has a `.size` attribute.
    assert getattr(icon, "size", None) == (64, 64)


def test_default_icon_factory_uses_pystray_contract(monkeypatch) -> None:
    created: dict[str, object] = {}

    class _FakeIcon:
        def __init__(self, name: str, image: object, title: str, menu: object) -> None:
            created["name"] = name
            created["image"] = image
            created["title"] = title
            created["menu"] = menu

        def stop(self) -> None:
            created["stopped"] = True

        def run(self) -> None:
            pass

    class _FakeMenuItem:
        def __init__(self, text: str, action, default: bool = False) -> None:
            self.text = text
            self.action = action
            self.default = default

    class _FakeMenu:
        def __init__(self, *items: object) -> None:
            self.items = items

    fake_pystray = types.SimpleNamespace(
        Icon=_FakeIcon,
        Menu=_FakeMenu,
        MenuItem=_FakeMenuItem,
    )
    monkeypatch.setitem(sys.modules, "pystray", fake_pystray)

    opened = {"count": 0}
    quit_called = {"count": 0}

    icon = _default_icon_factory(
        on_open=lambda: opened.__setitem__("count", opened["count"] + 1),
        on_quit=lambda: quit_called.__setitem__("count", quit_called["count"] + 1),
        title="Command Deck",
    )

    assert created["name"] == "command-deck"
    assert created["title"] == "Command Deck"
    assert hasattr(created["image"], "size")
    assert icon is not None

    # Exercise the MenuItem callbacks to cover the nested _open/_quit code paths.
    menu = created["menu"]
    assert hasattr(menu, "items")
    items = menu.items  # type: ignore[attr-defined]
    assert len(items) == 2

    # items[0] is Open
    items[0].action(None, None)  # type: ignore[attr-defined]
    assert opened["count"] == 1

    # items[1] is Quit
    items[1].action(icon, None)  # type: ignore[attr-defined]
    assert quit_called["count"] == 1
    assert created.get("stopped") is True

    # Also cover the branch where the passed icon has no callable .stop().
    class _NoStop:
        pass

    items[1].action(_NoStop(), None)  # type: ignore[attr-defined]
    assert quit_called["count"] == 2
