#!/usr/bin/env python3
"""Build script for packaging the Command Deck runtime into CommandDeck.exe.

This mirrors the ED runtime build philosophy:
- Build a self-contained onefile EXE with Nuitka
- End users do not need a system Python

Runtime behaviour (CommandDeck.exe):
- Starts FastAPI backend (uvicorn) in-process on http://127.0.0.1:8001
- Provides a tray icon with Open Command Deck + Quit
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List

APP_NAME = "Command Deck"
APP_ID = "CommandDeck"
RUNTIME_EXE_NAME = "CommandDeck"


def _ensure_frontend_dist_built(project_root: Path) -> None:
    """Ensure `frontend/dist` exists.

    The installed runtime serves the production UI build from the backend.
    """

    frontend_dir = project_root / "frontend"
    if not frontend_dir.exists():
        return

    dist_dir = frontend_dir / "dist"
    try:
        if dist_dir.exists() and any(dist_dir.iterdir()):
            return
    except OSError:
        return

    # Best-effort: only run npm build if the user has Node/npm available.
    try:
        subprocess.run(
            ["npm", "--prefix", str(frontend_dir), "run", "build"],
            check=False,
        )
    except OSError:
        return


def _preferred_python_exe(project_root: Path) -> str:
    """Prefer the repo venv interpreter even if the caller forgot to activate it."""

    venv_py = project_root / "venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable


def build_runtime() -> None:
    project_root = Path(__file__).resolve().parent
    python_exe = _preferred_python_exe(project_root)

    # Ensure frontend production build exists for inclusion/self-heal.
    _ensure_frontend_dist_built(project_root)

    runtime_entry = project_root / "backend" / "runtime_entry.py"
    if not runtime_entry.exists():
        raise FileNotFoundError(
            f"Could not find runtime entry at: {runtime_entry}\n"
            "Ensure backend/runtime_entry.py exists before building the runtime."
        )

    icon_path = project_root / f"{APP_ID}.ico"
    if not icon_path.exists():
        helper = project_root / "buildicon.py"
        subprocess.run([sys.executable, str(helper)], check=False)
    if not icon_path.exists():
        raise FileNotFoundError(
            f"Could not find {APP_ID}.ico at: {icon_path}\n"
            "Run `python buildicon.py` to generate it."
        )

    print(f"[buildruntime] Building runtime for {APP_NAME}")
    print(f"[buildruntime] Runtime entry script: {runtime_entry}")
    print(f"[buildruntime] Icon: {icon_path}")

    cpu_count = os.cpu_count() or 1
    jobs = str(cpu_count)

    debug_console = os.environ.get("COMMANDDECK_DEBUG_CONSOLE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    console_mode = "attach" if debug_console else "disable"
    print(f"[buildruntime] Windows console mode: {console_mode}")

    nuitka_args: List[str] = [
        python_exe,
        "-m",
        "nuitka",
        "--onefile",
        # Runtime does not use Qt directly, but the repo already depends on
        # PySide6 for the installer and icon tooling. Keeping the plugin enabled
        # is harmless and matches our existing ED-style packaging approach.
        "--enable-plugin=pyside6",
        f"--jobs={jobs}",
        f"--windows-console-mode={console_mode}",
        f"--output-filename={RUNTIME_EXE_NAME}.exe",
        f"--windows-icon-from-ico={icon_path}",
    ]

    # Ensure backend/app is importable as `app.*` in the compilation environment.
    # (We also bundle backend/ as payload data for the installed app.)
    nuitka_args.append("--include-package=app")
    nuitka_args.append("--include-package=uvicorn")

    # Tray dependencies are imported dynamically inside runtime_entry.py, so we
    # must force-include them for Nuitka.
    nuitka_args.append("--include-package=pystray")
    nuitka_args.append("--include-package=PIL")

    # pystray on Windows uses pywin32 modules that are also dynamically loaded.
    # Force-include the key win32 modules so the onefile runtime can start.
    nuitka_args.append("--include-module=pythoncom")
    nuitka_args.append("--include-module=pywintypes")
    nuitka_args.append("--include-module=win32api")
    nuitka_args.append("--include-module=win32con")
    nuitka_args.append("--include-module=win32gui")
    nuitka_args.append("--include-module=win32event")

    # Bundle the icon file so the runtime can use it for the tray icon even if
    # the installed payload copy goes missing.
    nuitka_args.append(f"--include-data-file={icon_path}={APP_ID}.ico")

    # Include the production frontend build so the runtime can self-heal if the
    # installer payload copy is missing.
    frontend_dist = project_root / "frontend" / "dist"
    if frontend_dist.exists():
        nuitka_args.append(f"--include-data-dir={frontend_dist}=frontend/dist")

    # Finally, the script to compile.
    nuitka_args.append(str(runtime_entry))

    print("[buildruntime] Running Nuitka with args:")
    for part in nuitka_args:
        print("  ", part)

    env = dict(os.environ)
    backend_dir = str(project_root / "backend")
    env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")

    result = subprocess.run(nuitka_args, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Nuitka build failed with exit code {result.returncode}")

    dist_path = project_root / f"{RUNTIME_EXE_NAME}.exe"
    if dist_path.exists():
        print(f"[buildruntime] Runtime build complete: {dist_path}")
    else:
        print(f"[buildruntime] Build finished but {dist_path} not found.")


def main() -> int:
    try:
        build_runtime()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[buildruntime] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
