# <img width="36" height="36" alt="CommandDeck" src="https://github.com/user-attachments/assets/256532ed-44e9-438c-9283-7c2214471155" /> Command Deck

Command Deck is a session-driven focus tool for moving **Tasks** through a fixed 4-stage workflow.

It is intentionally minimal: one board, one active session, clear stage focus.

Docs:

- Runtime design and code map: [`ARCHITECTURE.md`](ARCHITECTURE.md)

______________________________________________________________________

## Model

Work is organised into **four fixed stages** (stable internal IDs):

`DESIGN` · `BUILD` · `REVIEW` · `COMPLETE`

The stage *labels* are renameable per board, but the number of stages and ordering remain fixed.

______________________________________________________________________

## Tasks (internal name: Commands)

In the UI we call items **Tasks**. Internally (DB/API) they are still called **Commands**.

Each task belongs to a stage and progresses through a simple status model:

- Not Started
- In Progress
- Blocked
- Complete

Tasks are not plans.
They are small, active units of execution.

______________________________________________________________________

## Sessions

Time is tracked at the **task level**.

Only one session can be active at a time.

Starting a session requires selecting a task; the task's stage is pinned on the session row at start.

______________________________________________________________________

## Outcomes

Outcomes record what actually happened.

They are attached to commands and form a historical trace of execution.

______________________________________________________________________

## Interface

The system is presented as a single board with four stage columns.

Global controls live in the top bar:

- **Start** (enters selection mode; click a task to begin)
- **Add** (adds a task to the focused/active stage)
- **Stop** (stops the active session)

The active stage is visually dominant; inactive stages dim slightly.

______________________________________________________________________

## Philosophy

Command Deck does not optimise tasks.

It exposes operational state.

It exists to answer:

- What am I doing?
- What is in motion?
- What actually happened?

______________________________________________________________________

## Storage

A simple SQLite database is used for persistence.

Runtime notes:

- In dev/source runs, the default DB location is per-user app data (Windows: `LOCALAPPDATA`/`APPDATA`). See [`_default_sqlite_path()`](backend/app/core/config.py:44).
- In packaged/runtime installs, the default DB location is next to the runtime EXE. See [`_default_sqlite_path()`](backend/app/core/config.py:59).
- Override with `COMMANDDECK_SQLITE_PATH`. See [`_default_sqlite_path()`](backend/app/core/config.py:55).

Related runtime environment variables:

- `COMMANDDECK_SQLITE_PATH` — override SQLite DB file path.
- `COMMANDDECK_FRONTEND_DIST_DIR` — override the production frontend dist directory used for static serving (mainly for tests). See [`frontend_dist_dir()`](backend/app/core/static_files.py:27).

The system is intentionally minimal.

______________________________________________________________________

## Development: Run Locally

Command Deck v1 is local-only and intended to run on:

- backend: `http://127.0.0.1:8001`
- frontend (dev server): `http://127.0.0.1:5173`

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

The frontend dev server proxies `/api/*` to the backend.

### 2b) Frontend production build served by the backend

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

### 3) Tests (backend)

Backend tests are full-stack (API → services → repositories → real SQLite) and must run at 100% coverage:

```powershell
./venv/Scripts/Activate.ps1
pytest -v --cov
```

### 4) Quality gates (backend)

Run from repo root:

```powershell
./venv/Scripts/Activate.ps1
python -m black --check backend
python -m flake8 backend
python -m mypy backend/app
python -m pytest -q
```

______________________________________________________________________

## Tray runtime (Windows-only)

Command Deck v1 includes a minimal system tray launcher.

It:

- starts the backend server in the background
- provides tray menu actions:
  - **Open Command Deck** (opens default browser to `http://127.0.0.1:8001/`)
  - **Quit** (stops backend + exits tray)

Run it from the repo root:

```powershell
./venv/Scripts/Activate.ps1
cd backend
python -m app.tray
```

______________________________________________________________________

## Windows release: packaged runtime + GUI installer

Command Deck ships a self-contained Windows runtime executable and a GUI
installer, both built with Nuitka.

Single source of truth for versioning:

- [`backend/app/version.py`](backend/app/version.py:1) (`VERSION = "x.y.z"`)

### 1) Prerequisites (build machine)

- Python (use the repo `venv`)
- Visual Studio Build Tools (MSVC) for Nuitka C compilation
- Node.js + npm (to build the frontend production bundle)

### 2) One-time environment setup

From repo root:

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

### 3) Build icon (.ico)

The runtime and installer use the repo-root icon file:

- [`CommandDeck.ico`](CommandDeck.ico)

If you need to regenerate it, run:

```powershell
./venv/Scripts/Activate.ps1
python buildicon.py
```

Note: [`buildicon.py`](buildicon.py:1) rasterizes an SVG input. If you don't have
an SVG source available in `frontend/public/`, keep using the existing
[`CommandDeck.ico`](CommandDeck.ico).

This writes `CommandDeck.ico` in the repo root and is used consistently for:

- installer window icon
- packaged installer icon
- shortcuts icon
- Add/Remove Programs icon

### 4) Build the packaged runtime (CommandDeck.exe)

`CommandDeck.exe` is the installed runtime entrypoint targeted by shortcuts.
It hosts the tray and starts the FastAPI backend in-process.

```powershell
./venv/Scripts/Activate.ps1
python buildruntime.py
```

Output:

- `CommandDeck.exe`

### Packaged runtime behavior (high-level)

The packaged runtime entrypoint is [`backend/runtime_entry.py`](backend/runtime_entry.py:1). It:

- enforces a single running instance (Windows file lock under LocalAppData)
- starts the FastAPI app via uvicorn **in-process** (no external Python required)
- serves the built frontend from the same address when `frontend/dist` exists
- writes diagnostic logs next to the EXE (`CommandDeck-runtime.log`)
- can restore a missing `frontend/dist` from embedded resources on first run

### 5) Build the GUI installer (CommandDeckInstaller.exe)

The installer bundles a curated payload directory, including:

- `CommandDeck.exe`
- `backend/` (as data payload)
- `frontend/` including `frontend/dist` production build
- `LICENSE` (product license)
- `INSTALLER_LICENSE` (installer UI license)

```powershell
./venv/Scripts/Activate.ps1
python buildguiinstaller.py
```

Output:

- `CommandDeckInstaller.exe`

______________________________________________________________________

## Database persistence (Windows installer)

The application stores its SQLite database next to the installed runtime EXE:

- `command_deck.db` (plus optional SQLite sidecars `command_deck.db-wal` and `command_deck.db-shm`)

Installer behavior:

- **Repair**: never touches the database.
- **Uninstall**: preserves the database by default.
  - To wipe user data, use the **"On uninstall, also delete my database"** checkbox.
