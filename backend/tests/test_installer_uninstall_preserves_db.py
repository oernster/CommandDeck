from __future__ import annotations

from pathlib import Path

import pytest


def _import_guiinstaller_or_skip():
    """Import guiinstaller.py and skip if PySide6 isn't available in test env."""

    pytest.importorskip("PySide6")
    import guiinstaller  # type: ignore

    return guiinstaller


def test_uninstall_preserves_db_by_default(tmp_path: Path) -> None:
    guiinstaller = _import_guiinstaller_or_skip()

    install_dir = tmp_path / "CommandDeck"
    install_dir.mkdir(parents=True, exist_ok=True)

    # Simulate an installed layout.
    (install_dir / "CommandDeck.exe").write_text("", encoding="utf-8")
    (install_dir / "some_file.txt").write_text("x", encoding="utf-8")

    # User data: DB + WAL/SHM sidecars.
    db = install_dir / guiinstaller.SQLITE_DB_FILENAME
    wal = Path(str(db) + "-wal")
    shm = Path(str(db) + "-shm")
    db.write_text("db", encoding="utf-8")
    wal.write_text("wal", encoding="utf-8")
    shm.write_text("shm", encoding="utf-8")

    class _Dummy:
        def _log(self, *_args, **_kwargs):  # noqa: ANN002
            return

        def _update_progress(self) -> None:
            return

    dummy = _Dummy()
    preserve = guiinstaller.InstallerWindow._sqlite_related_paths(dummy, db)
    guiinstaller.InstallerWindow._delete_tree(dummy, install_dir, preserve_paths=preserve)

    assert db.exists()
    assert wal.exists()
    assert shm.exists()
    assert not (install_dir / "some_file.txt").exists()
    # Root should remain because we preserved files.
    assert install_dir.exists()


def test_uninstall_wipe_data_deletes_db_and_sidecars(tmp_path: Path) -> None:
    guiinstaller = _import_guiinstaller_or_skip()

    install_dir = tmp_path / "CommandDeck"
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "some_file.txt").write_text("x", encoding="utf-8")

    db = install_dir / guiinstaller.SQLITE_DB_FILENAME
    wal = Path(str(db) + "-wal")
    shm = Path(str(db) + "-shm")
    db.write_text("db", encoding="utf-8")
    wal.write_text("wal", encoding="utf-8")
    shm.write_text("shm", encoding="utf-8")

    class _Dummy:
        def _log(self, *_args, **_kwargs):  # noqa: ANN002
            return

        def _update_progress(self) -> None:
            return

    dummy = _Dummy()
    guiinstaller.InstallerWindow._delete_tree(dummy, install_dir, preserve_paths=None)

    assert not db.exists()
    assert not wal.exists()
    assert not shm.exists()
    assert not (install_dir / "some_file.txt").exists()
    assert not install_dir.exists()

