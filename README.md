# Command Deck

Command Deck is an operational system for issuing intent, tracking execution, and recording outcomes.

It is not a task manager.

It is a control surface.

---

## Model

Work is organised into five operational categories:

[ DESIGN ]   [ BUILD ]   [ REVIEW ]   [ MAINTAIN ]   [ RECOVER ]

These form a continuous loop of operation.

---

## Commands

Commands represent intent.

Each command belongs to a category and progresses through a simple state model:

- Not Started
- In Progress
- Blocked
- Complete

Commands are not plans.
They are active units of execution.

---

## Sessions

Time is tracked at the category level.

Only one category is active at a time.

A session represents a period of focused operation within a category.

---

## Outcomes

Outcomes record what actually happened.

They are attached to commands and form a historical trace of execution.

---

## Interface

The system is presented as a single operational surface:

[ Command Deck ]

[ DESIGN ]   [ BUILD ]   [ REVIEW ]   [ MAINTAIN ]   [ RECOVER ]

Each column contains commands:

[ Command Title        ] 🔴
[ Command Title        ] 🟠
[ Command Title        ] 🟢

+ Add Command

A session panel provides:

- Active session timer
- Start / Stop control
- Current category

---

## Philosophy

Command Deck does not optimise tasks.

It exposes operational state.

It exists to answer:

- What am I doing?
- What is in motion?
- What actually happened?

---

## Storage

A simple SQLite database is used for persistence.

Runtime notes:

- In dev/source runs, the default DB location is per-user app data (Windows: `LOCALAPPDATA`/`APPDATA`). See [`_default_sqlite_path()`](backend/app/core/config.py:44).
- Override with `COMMANDDECK_SQLITE_PATH`. See [`_default_sqlite_path()`](backend/app/core/config.py:55).

The system is intentionally minimal.

---

## Development: Run Locally

Command Deck v1 is local-only and intended to run on:

* backend: `http://127.0.0.1:8001`
* frontend (dev server): `http://127.0.0.1:5173`

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

* `GET http://127.0.0.1:8001/api/health`

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

* `http://127.0.0.1:8001/`

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
python -m pytest -q backend --cov=backend/app --cov-fail-under=100
```

---

## Tray runtime (Windows-only)

Command Deck v1 includes a minimal system tray launcher.

It:

* starts the backend server in the background
* provides tray menu actions:
  * **Open Command Deck** (opens default browser to `http://127.0.0.1:8001/`)
  * **Quit** (stops backend + exits tray)

Run it from the repo root:

```powershell
./venv/Scripts/Activate.ps1
cd backend
python -m app.tray
```

---

## Windows release: packaged runtime + GUI installer

Command Deck ships a self-contained Windows runtime executable and a GUI
installer, both built with Nuitka.

Single source of truth for versioning:

* [`backend/app/version.py`](backend/app/version.py:1) (`VERSION = "x.y.z"`)

### 1) Prerequisites (build machine)

* Python (use the repo `venv`)
* Visual Studio Build Tools (MSVC) for Nuitka C compilation
* Node.js + npm (to build the frontend production bundle)

### 2) One-time environment setup

From repo root:

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

### 3) Build icon (.ico) from existing favicon asset

Source-of-truth icon is:

* [`frontend/public/favicon.svg`](frontend/public/favicon.svg:1)

Generate the Windows icon file:

```powershell
./venv/Scripts/Activate.ps1
python buildicon.py
```

This writes `CommandDeck.ico` in the repo root and is used consistently for:

* installer window icon
* packaged installer icon
* shortcuts icon
* Add/Remove Programs icon

### 4) Build the packaged runtime (CommandDeck.exe)

`CommandDeck.exe` is the installed runtime entrypoint targeted by shortcuts.
It hosts the tray and starts the FastAPI backend in-process.

```powershell
./venv/Scripts/Activate.ps1
python buildruntime.py
```

Output:

* `CommandDeck.exe`

### 5) Build the GUI installer (CommandDeckInstaller.exe)

The installer bundles a curated payload directory, including:

* `CommandDeck.exe`
* `backend/` (as data payload)
* `frontend/` including `frontend/dist` production build
* `LICENSE` (product license)
* `INSTALLER_LICENSE` (installer UI license)

```powershell
./venv/Scripts/Activate.ps1
python buildguiinstaller.py
```

Output:

* `CommandDeckInstaller.exe`
