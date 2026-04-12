from __future__ import annotations

import builtins
import sys
from pathlib import Path

from app.core import config
from app.core import static_files


def test_runtime_root_dir_uses_exe_dir_when_frozen(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "CommandDeck.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [str(exe)], raising=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert static_files._runtime_root_dir() == tmp_path


def test_runtime_root_dir_uses_repo_root_when_not_frozen(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    root = static_files._runtime_root_dir()

    # In source mode this should resolve to the repo root that contains backend/.
    assert (root / "backend").is_dir()


def test_frontend_dist_dir_override(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "some" / "frontend" / "dist"
    override.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("COMMANDDECK_FRONTEND_DIST_DIR", str(override))
    assert static_files.frontend_dist_dir() == override.resolve()


def test_frontend_dist_dir_prefers_installed_layout(monkeypatch, tmp_path: Path) -> None:
    install_root = tmp_path / "Install"
    exe = install_root / "CommandDeck.exe"
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text("", encoding="utf-8")

    dist_dir = install_root / "frontend" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    (dist_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.delenv("COMMANDDECK_FRONTEND_DIST_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", [str(exe)], raising=True)

    assert static_files.frontend_dist_dir() == dist_dir


def test_frontend_dist_dir_falls_back_to_default_guess(monkeypatch) -> None:
    """Cover the default-path branch when no `index.html` checks succeed."""

    monkeypatch.delenv("COMMANDDECK_FRONTEND_DIST_DIR", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)

    # Prevent both the installed-layout check and the extracted-data search from
    # discovering any real `index.html` in the repo.
    monkeypatch.setattr(static_files.Path, "is_file", lambda _self: False, raising=True)

    expected = static_files._runtime_root_dir() / "frontend" / "dist"
    assert static_files.frontend_dist_dir() == expected


def test_frontend_dist_dir_installed_check_exception_path(monkeypatch) -> None:
    """Cover the `except` path when `Path(sys.argv[0])` cannot be built."""

    monkeypatch.delenv("COMMANDDECK_FRONTEND_DIST_DIR", raising=False)
    monkeypatch.setattr(sys, "argv", [None], raising=True)

    # Should not raise; should fall back to a usable path.
    out = static_files.frontend_dist_dir()
    assert isinstance(out, Path)


def test_runtime_root_dir_handles_import_exception(monkeypatch) -> None:
    """Cover the defensive `except` in `_runtime_root_dir()` (lines 18-19)."""

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "sys":
            raise ImportError("boom")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import, raising=True)
    root = static_files._runtime_root_dir()
    assert (root / "backend").is_dir()


def test_frontend_dist_dir_handles_extract_search_exception(
    monkeypatch, tmp_path: Path
) -> None:
    """Cover the defensive `except` in the extracted-data search (lines 56-57)."""

    monkeypatch.delenv("COMMANDDECK_FRONTEND_DIST_DIR", raising=False)

    # Make the installed-layout check raise before it calls `.resolve()`.
    monkeypatch.setattr(sys, "argv", [None], raising=True)

    # Make Path.resolve raise during the extracted-data search.
    # Also stub `_runtime_root_dir()` so the default-guess branch doesn't depend
    # on `Path.resolve()` (which `_runtime_root_dir()` uses).
    monkeypatch.setattr(static_files, "_runtime_root_dir", lambda: tmp_path, raising=True)

    def _boom(self, *args, **kwargs):  # noqa: ANN001, D401
        raise RuntimeError("boom")

    monkeypatch.setattr(static_files.Path, "resolve", _boom, raising=True)

    # Should not raise; should fall back to runtime-root guess.
    out = static_files.frontend_dist_dir()
    assert isinstance(out, Path)


def test_config_runtime_root_returns_exe_dir_when_frozen(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "CommandDeck.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [str(exe)], raising=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    # Ensure the frozen branch is exercised (the exe-name branch runs first).
    monkeypatch.setattr(config.os.path, "basename", lambda _: "python.exe", raising=True)

    assert config._runtime_root() == str(tmp_path)


def test_config_runtime_root_handles_exception_and_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", [], raising=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    # With sys.argv empty, accessing argv[0] would raise; we should fall back.
    out = config._runtime_root()
    assert isinstance(out, str)
    assert out


def test_config_runtime_root_handles_argv0_str_exception(monkeypatch) -> None:
    """Cover the defensive `except` in the argv0/exe-name probe inside `_runtime_root()`."""

    class _BadStr:
        def __str__(self) -> str:  # noqa: D401
            raise RuntimeError("boom")

    monkeypatch.setattr(sys, "argv", [_BadStr()], raising=True)
    monkeypatch.delattr(sys, "frozen", raising=False)

    out = config._runtime_root()
    assert isinstance(out, str)
    assert out
    # In source mode this should resolve to the repo root that contains backend/.
    assert (Path(out) / "backend").is_dir()


def test_config_runtime_root_uses_repo_root_when_not_frozen(monkeypatch) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    root = config._runtime_root()
    # In source mode this should resolve to the repo root that contains backend/.
    assert (Path(root) / "backend").is_dir()


def test_default_sqlite_path_windows_no_appdata_falls_back_to_home(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "win32", raising=False)

    # Make expanduser deterministic.
    monkeypatch.setattr(config.os.path, "expanduser", lambda _: str(tmp_path), raising=True)
    out = config._default_sqlite_path()
    assert out == str(tmp_path / ".commanddeck" / "command_deck.db")


def test_default_sqlite_path_uses_localappdata_when_not_frozen(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    out = config._default_sqlite_path()
    assert str(tmp_path) in out
    assert out.endswith("command_deck.db")


def test_default_sqlite_path_uses_exe_dir_when_frozen(monkeypatch, tmp_path: Path) -> None:
    exe = tmp_path / "CommandDeck.exe"
    exe.write_text("", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [str(exe)], raising=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)

    out = config._default_sqlite_path()
    assert out == str(tmp_path / "command_deck.db")


def test_default_sqlite_path_respects_override_env(monkeypatch) -> None:
    monkeypatch.setenv("COMMANDDECK_SQLITE_PATH", "C:/tmp/override.db")
    out = config._default_sqlite_path()
    assert out.replace("\\", "/").endswith("/tmp/override.db")


def test_config_runtime_root_prefers_commanddeck_exe_even_when_not_frozen(monkeypatch, tmp_path: Path) -> None:
    # Cover the argv0 exe-name branch in `_runtime_root()`.
    exe = tmp_path / "CommandDeck.exe"
    monkeypatch.setattr(sys, "argv", [str(exe)], raising=True)
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert config._runtime_root() == str(tmp_path)


def test_default_sqlite_path_handles_exe_check_exception(monkeypatch, tmp_path: Path) -> None:
    class _BadStr:
        def __str__(self) -> str:  # noqa: D401
            raise RuntimeError("boom")

    monkeypatch.setattr(sys, "argv", [_BadStr()], raising=True)
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    out = config._default_sqlite_path()
    assert out == str(tmp_path / "CommandDeck" / "command_deck.db")


def test_default_sqlite_path_falls_back_to_home_when_no_appdata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(sys, "platform", "linux", raising=False)

    # Make expanduser deterministic.
    monkeypatch.setattr(config.os.path, "expanduser", lambda _: str(tmp_path), raising=True)
    out = config._default_sqlite_path()
    assert out == str(tmp_path / ".commanddeck" / "command_deck.db")


def test_default_sqlite_path_exe_branch_exception_is_defensive(monkeypatch, tmp_path: Path) -> None:
    # Cover the `except Exception` around argv0 parsing.
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    class _Bad:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    monkeypatch.setattr(sys, "argv", [_Bad()], raising=True)
    monkeypatch.delattr(sys, "frozen", raising=False)

    out = config._default_sqlite_path()
    assert out == str(tmp_path / "CommandDeck" / "command_deck.db")


def test_default_sqlite_path_uses_repo_root_when_runtime_root_used(monkeypatch, tmp_path: Path) -> None:
    # Cover the exe-name branch.
    monkeypatch.delenv("COMMANDDECK_SQLITE_PATH", raising=False)
    monkeypatch.setattr(config, "_runtime_root", lambda: str(tmp_path), raising=True)
    monkeypatch.setattr(sys, "argv", [str(tmp_path / "CommandDeck.exe")], raising=True)
    monkeypatch.delattr(sys, "frozen", raising=False)

    out = config._default_sqlite_path()
    assert out == str(tmp_path / "command_deck.db")

