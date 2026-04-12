#!/usr/bin/env python3
"""Build script for packaging the Command Deck GUI installer into a Windows EXE.

Mirrors the EDColonisationAsst build philosophy:
- Nuitka onefile packaging
- Bundled curated payload directory
- Bundled LICENSE + INSTALLER_LICENSE when present
- Explicit bundling of runtime EXE used by shortcuts: CommandDeck.exe

Versioning:
- Single source of truth is backend/app/version.py
- We do not create or bundle a top-level VERSION file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from iconutil import ensure_windows_ico

APP_NAME = "Command Deck"
INSTALLER_NAME = "CommandDeckInstaller"
APP_ID = "CommandDeck"
RUNTIME_EXE = "CommandDeck.exe"


def build_installer() -> None:
    project_root = Path(__file__).resolve().parent

    gui_script = project_root / "guiinstaller.py"
    if not gui_script.exists():
        raise FileNotFoundError(f"Could not find guiinstaller.py at: {gui_script}")

    # Ensure we have a Windows icon derived from the existing favicon SVG.
    icon_path = project_root / f"{APP_ID}.ico"
    if not icon_path.exists():
        _build_ico(project_root)
    if not icon_path.exists():
        raise FileNotFoundError(
            f"Could not find {APP_ID}.ico at: {icon_path}. "
            "Run `python buildicon.py` to generate it."
        )

    # Ensure the .ico we ship is a square, multi-size Windows icon. Some online
    # converters produce non-square entries (e.g. 32x31) that can appear blank
    # in Start Menu/Desktop shortcuts.
    ensure_windows_ico(icon_path)

    runtime_exe = project_root / RUNTIME_EXE
    if not runtime_exe.exists():
        raise FileNotFoundError(
            f"Could not find runtime EXE at: {runtime_exe}\n"
            "Run `python buildruntime.py` to build CommandDeck.exe before building the GUI installer."
        )

    license_file = project_root / "LICENSE"
    installer_license_file = project_root / "INSTALLER_LICENSE"

    _ensure_frontend_dist_built(project_root)

    payload_src = _ensure_payload_dir(project_root)

    print(f"[buildguiinstaller] Building installer for {APP_NAME}")
    print(f"[buildguiinstaller] GUI script: {gui_script}")
    print(f"[buildguiinstaller] Icon: {icon_path}")
    print(f"[buildguiinstaller] Embedding payload from: {payload_src}")

    cpu_count = os.cpu_count() or 1
    jobs = str(cpu_count)
    print(f"[buildguiinstaller] Using {jobs} parallel jobs for Nuitka compilation")

    nuitka_args: List[str] = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--enable-plugin=pyside6",
        f"--jobs={jobs}",
        "--windows-console-mode=disable",
        f"--output-filename={INSTALLER_NAME}.exe",
        f"--windows-icon-from-ico={icon_path}",
    ]

    if payload_src.exists():
        nuitka_args.append(f"--include-data-dir={payload_src}=payload")

    nuitka_args.append(f"--include-data-file={runtime_exe}=runtime/{RUNTIME_EXE}")

    if license_file.exists():
        nuitka_args.append(f"--include-data-file={license_file}=LICENSE")
    if installer_license_file.exists():
        nuitka_args.append(
            f"--include-data-file={installer_license_file}=INSTALLER_LICENSE"
        )
    if icon_path.exists():
        nuitka_args.append(f"--include-data-file={icon_path}={APP_ID}.ico")

    nuitka_args.append(str(gui_script))

    print("[buildguiinstaller] Running Nuitka with args:")
    for part in nuitka_args:
        print("  ", part)

    result = subprocess.run(nuitka_args)
    if result.returncode != 0:
        raise RuntimeError(f"Nuitka build failed with exit code {result.returncode}")

    dist_path = project_root / f"{INSTALLER_NAME}.exe"
    if dist_path.exists():
        print(f"[buildguiinstaller] Build complete: {dist_path}")
    else:
        print(f"[buildguiinstaller] Build finished but {dist_path} not found.")


def _build_ico(project_root: Path) -> None:
    helper = project_root / "buildicon.py"
    if not helper.exists():
        raise FileNotFoundError(f"buildicon.py not found at: {helper}")
    result = subprocess.run([sys.executable, str(helper)], check=False)
    if result.returncode != 0:
        raise RuntimeError("buildicon.py failed to generate the .ico")


def _ensure_frontend_dist_built(project_root: Path) -> None:
    frontend_dir = project_root / "frontend"
    if not frontend_dir.exists():
        print("[buildguiinstaller] frontend/ not found; skipping frontend build.")
        return

    dist_dir = frontend_dir / "dist"
    try:
        if dist_dir.exists() and any(dist_dir.iterdir()):
            print(f"[buildguiinstaller] Using existing frontend build at: {dist_dir}")
            return
    except OSError as exc:
        raise RuntimeError(f"Unable to inspect frontend/dist: {exc}") from exc

    print("[buildguiinstaller] frontend/dist missing; running `npm run build`...")
    try:
        result = subprocess.run(
            ["npm", "--prefix", str(frontend_dir), "run", "build"],
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(
            "Failed to start npm to build the frontend. Ensure Node.js/npm are on PATH. "
            f"Underlying error: {exc}"
        ) from exc

    if result.returncode != 0:
        raise RuntimeError("`npm run build` failed; inspect npm output and retry.")

    try:
        if not dist_dir.exists() or not any(dist_dir.iterdir()):
            raise RuntimeError("frontend/dist still missing/empty after build")
    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect frontend/dist after build: {exc}"
        ) from exc

    print(f"[buildguiinstaller] Frontend production build ready at: {dist_dir}")


def _ensure_payload_dir(project_root: Path) -> Path:
    payload_dir = project_root / "build_payload"
    if payload_dir.exists():
        shutil.rmtree(payload_dir)
    payload_dir.mkdir(parents=True, exist_ok=True)

    curated_files = [
        f"{APP_ID}.ico",
        "LICENSE",
        RUNTIME_EXE,
    ]

    curated_dirs = [
        "backend",
        "frontend",
    ]

    ignore_dir_names = {
        ".git",
        ".venv",
        ".benchmarks",
        "htmlcov",
        ".pytest_cache",
        "__pycache__",
        "tests",
        "node_modules",
    }
    ignore_file_names = {
        ".coverage",
        ".git",
        ".gitignore",
        "guiinstaller.log",
        ".env",
        "pytest.ini",
        "requirements-dev.txt",
        "requirements-dev-linux.txt",
        # Never ship user data in the installer payload.
        "command_deck.db",
    }

    def _ignore_unwanted(_: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if name in ignore_dir_names or name in ignore_file_names:
                ignored.add(name)
        return ignored

    for name in curated_files:
        src = project_root / name
        if src.exists():
            dst = payload_dir / name
            shutil.copy2(src, dst)
            print(f"[buildguiinstaller] Payload file: {src} -> {dst}")

    for name in curated_dirs:
        src = project_root / name
        if src.exists():
            dst = payload_dir / name
            shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore_unwanted)
            print(f"[buildguiinstaller] Payload dir:  {src} -> {dst}")

            if name == "frontend":
                dist_src = src / "dist"
                dist_dst = dst / "dist"
                if dist_src.exists():
                    shutil.copytree(dist_src, dist_dst, dirs_exist_ok=True)
                    print(
                        "[buildguiinstaller] Payload frontend build: "
                        f"{dist_src} -> {dist_dst}"
                    )
                else:
                    print(
                        "[buildguiinstaller] WARNING: frontend/dist not found; "
                        "installed app will not serve the web UI."
                    )

    # Work around data-dir stripping: ship backend sources as *.py_ then restore on install.
    backend_payload = payload_dir / "backend"
    if backend_payload.exists():
        for py_file in backend_payload.rglob("*.py"):
            # Rename "x.py" -> "x.py_" so Nuitka doesn't strip python sources
            # from data directories.
            renamed = py_file.with_name(py_file.name + "_")
            py_file.rename(renamed)

    try:
        has_entries = any(payload_dir.iterdir())
    except OSError as exc:
        raise RuntimeError(
            f"Unable to inspect payload directory '{payload_dir}': {exc}"
        ) from exc

    if not has_entries:
        raise RuntimeError(f"Bootstrapped payload directory '{payload_dir}' is empty.")

    print(f"[buildguiinstaller] Bootstrapped payload directory at: {payload_dir}")
    return payload_dir


def main() -> int:
    try:
        build_installer()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[buildguiinstaller] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
