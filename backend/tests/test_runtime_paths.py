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

    assert config._runtime_root() == str(tmp_path)


def test_config_runtime_root_handles_exception_and_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", [], raising=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    # With sys.argv empty, accessing argv[0] would raise; we should fall back.
    out = config._runtime_root()
    assert isinstance(out, str)
    assert out

