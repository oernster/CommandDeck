from __future__ import annotations

from pathlib import Path

import pytest

from app import version
from app.main import app

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / version.VERSION_FILENAME


def _repo_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def test_version_comes_from_the_repo_root_version_file() -> None:
    assert version.VERSION == _repo_version()


def test_fastapi_metadata_carries_the_version_file() -> None:
    assert app.version == _repo_version()


def test_read_version_skips_missing_and_empty_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing" / "VERSION"
    empty = tmp_path / "empty"
    empty.write_text("  \n", encoding="utf-8")
    real = tmp_path / "real"
    real.write_text("9.8.7\n", encoding="utf-8")

    assert version.read_version([missing, empty, real]) == "9.8.7"


def test_read_version_falls_back_when_no_file_is_readable(tmp_path: Path) -> None:
    assert version.read_version([tmp_path / "VERSION"]) == version.FALLBACK_VERSION


def test_installer_reads_the_version_file() -> None:
    pytest.importorskip("PySide6")
    import guiinstaller  # type: ignore

    assert guiinstaller.get_backend_version() == _repo_version()
