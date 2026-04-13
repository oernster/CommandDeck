# Command Deck — Developer Guide

This guide is for contributors and developers building/running Command Deck from source, running tests/quality gates, or producing Windows release artifacts.

User-facing overview lives in [`README.md`](README.md). Runtime architecture and code map lives in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Runtime addresses (v1)

- Backend API: `http://127.0.0.1:8001`
- Frontend dev server: `http://127.0.0.1:5173`

The frontend dev server proxies `/api/*` to the backend (see [`vite.config.ts`](frontend/vite.config.ts:1)).

---

## Prerequisites

For local development:

- Python 3.11 (recommended; backend tooling is configured for 3.11)
- Node.js + npm (frontend)

For Windows release builds (Nuitka):

- Visual Studio Build Tools (MSVC) so Nuitka can compile native code

Python dependencies are listed in [`requirements.txt`](requirements.txt).

---

## Run locally (source)

### 1) Backend (FastAPI)

From the repo root:

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt

# Run API on http://127.0.0.1:8001
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Health check:

- `GET http://127.0.0.1:8001/api/health`

### 2) Frontend (Vite + React)

In a separate terminal:

```powershell
cd frontend
npm install

# Run UI on http://127.0.0.1:5173
npm run dev -- --host 127.0.0.1 --port 5173
```

### 2b) Serve a production frontend build from the backend

To run the UI from the backend on a single address (`http://127.0.0.1:8001/`):

```powershell
cd frontend
npm install
npm run build

# In a separate terminal
cd ..
./venv/Scripts/Activate.ps1
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Then open:

- `http://127.0.0.1:8001/`

Static serving behavior is implemented in [`create_app()`](backend/app/main.py:32) and the dist-path resolution in [`frontend_dist_dir()`](backend/app/core/static_files.py:27).

---

## Storage (SQLite)

The backend uses SQLite for persistence; the DB file path is resolved by [`_default_sqlite_path()`](backend/app/core/config.py:44).

Defaults:

- Dev/source runs (Windows): under `LOCALAPPDATA`/`APPDATA` (never write DB files into the repo)
- Packaged/runtime installs: next to the runtime EXE

Override:

- `COMMANDDECK_SQLITE_PATH` — override the SQLite DB file path

Related runtime/testing variable:

- `COMMANDDECK_FRONTEND_DIST_DIR` — override the production frontend dist directory used for static serving (primarily for tests). See [`frontend_dist_dir()`](backend/app/core/static_files.py:27).

---

## Tests (backend)

Backend tests are full-stack (API → services → repositories → real SQLite) and enforce **100% coverage** via [`pyproject.toml`](pyproject.toml:1).

From the repo root:

```powershell
./venv/Scripts/Activate.ps1
pytest -v --cov
```

---

## Quality gates (backend)

From the repo root:

```powershell
./venv/Scripts/Activate.ps1
python -m black --check backend
python -m flake8 backend
python -m mypy backend/app
python -m pytest -q
```

---

## Tray runtime (Windows-only, source/dev)

Command Deck includes a minimal system tray launcher for Windows.

Entry point:

- [`backend/app/tray/__main__.py`](backend/app/tray/__main__.py:1)

Runtime logic:

- [`run_tray()`](backend/app/tray/runtime.py:161)

It:

- starts the backend server in the background (via `uvicorn`)
- provides tray menu actions:
  - **Open Command Deck** (opens default browser to `http://127.0.0.1:8001/`)
  - **Quit** (stops backend + exits tray)

Run it from the repo root:

```powershell
./venv/Scripts/Activate.ps1
cd backend
python -m app.tray
```

---

## Windows release: packaged runtime + GUI installer (Nuitka)

Command Deck ships a self-contained Windows runtime executable and a GUI installer, both built with Nuitka.

Single source of truth for versioning:

- [`VERSION`](backend/app/version.py:1) in `backend/app/version.py`

### Build-time environment variables

- `COMMANDDECK_DEBUG_CONSOLE` — when truthy (`1/true/yes/on`), the runtime build uses an attached console window. See [`build_runtime()`](buildruntime.py:62).

### 1) One-time environment setup

From repo root:

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

### 2) Build icon (.ico)

The runtime and installer use the repo-root icon file:

- [`CommandDeck.ico`](CommandDeck.ico)

To regenerate:

```powershell
./venv/Scripts/Activate.ps1
python buildicon.py
```

### 3) Build the packaged runtime (CommandDeck.exe)

`CommandDeck.exe` is the installed runtime entrypoint targeted by shortcuts.

Build:

```powershell
./venv/Scripts/Activate.ps1
python buildruntime.py
```

Output:

- `CommandDeck.exe`

The packaged runtime entrypoint is [`backend/runtime_entry.py`](backend/runtime_entry.py:1) (starts the backend in-process, enforces single-instance on Windows, self-heals missing `frontend/dist`, and hosts the tray).

### 4) Build the GUI installer (CommandDeckInstaller.exe)

Build:

```powershell
./venv/Scripts/Activate.ps1
python buildguiinstaller.py
```

Output:

- `CommandDeckInstaller.exe`

The installer bundles a curated payload directory, including:

- `CommandDeck.exe`
- `backend/` (payload)
- `frontend/` including `frontend/dist` production build
- [`LICENSE`](LICENSE)
- [`INSTALLER_LICENSE`](INSTALLER_LICENSE)

---

## Database persistence (Windows installer)

The application stores its SQLite database next to the installed runtime EXE:

- `command_deck.db` (plus optional SQLite sidecars `command_deck.db-wal` and `command_deck.db-shm`)

Installer behavior:

- **Repair**: never touches the database.
- **Uninstall**: preserves the database by default.
  - To wipe user data, use the **"On uninstall, also delete my database"** checkbox.

