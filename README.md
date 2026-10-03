# <img width="36" height="36" alt="CommandDeck" src="https://github.com/user-attachments/assets/256532ed-44e9-438c-9283-7c2214471155" /> Command Deck

Command Deck is a session-driven focus tool for moving **Tasks** through a fixed 4-stage workflow. It is intentionally minimal: one board, one active session, clear stage focus. It does not optimise tasks; it exposes operational state, to answer three questions: what am I doing, what is in motion and what actually happened.

> **Commercial licences available.** Command Deck is free and open source under GPL-3.0. If those terms do not suit what you are building, such as a closed-source product, a commercial licence can be bought from me separately. It covers my own code; PySide6 (LGPL-3.0) and the other third-party libraries keep their own licences. See [commercial licensing](https://ernster.dev/commercial-licensing.html).

<img width="3694" height="1898" alt="CommandDeck" src="https://github.com/user-attachments/assets/eebc232a-4d8a-4039-bb08-d83a454be576" />

Docs:

- Runtime design and code map: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Developer setup, local runs and packaging: [`DEVELOPMENT.md`](DEVELOPMENT.md)
- Tests and quality gates: [`TESTING.md`](TESTING.md)

---

## Who it is for and who it is not for

For one person on Windows who wants a single board showing the few tasks actually in motion, with the time spent on each and a record of what came of it.

Not for teams or shared boards: there are no accounts and no sync; everything lives in one local SQLite file. Not a planner: there is one board, no due dates and no backlog beyond the four stages.

---

## What it does

### Model

Work is organised into **four fixed stages** (stable internal IDs):

`DESIGN` · `BUILD` · `REVIEW` · `COMPLETE`

The stage *labels* are renameable per board; the number of stages and ordering remain fixed.

### Tasks (internal name: Commands)

In the UI we call items **Tasks**. Internally (DB/API) they are called **Commands**.

Each task belongs to a stage and progresses through a simple status model:

- Not Started
- In Progress
- Blocked
- Complete

Tasks are not plans. They are small, active units of execution. They can be renamed in place and dragged to reorder within a stage or to move to another stage; the order and the stage are saved.

### Sessions

Time is tracked at the **task level**.

Only one session can be active at a time: starting a new one ends any session still running.

Starting a session requires selecting a task; the task's stage is pinned on the session row at start.

### Outcomes

Outcomes record what actually happened.

They are attached to tasks and form a historical trace of execution. An outcome is never edited in place: editing the latest outcome saves a new entry.

### Interface

The system is presented as a single board with four stage columns. The board and each stage can be renamed.

Global controls live in the top bar:

- **Start** (enters selection mode; click a task to begin)
- **Add** (adds a task to the focused/active stage)
- **Stop** (stops the active session; shown in place of Start while a session runs)

The active stage is visually dominant; inactive stages dim slightly.

### Snapshots and reset

The **Snapshots** menu saves the whole board under a name, then loads, renames or deletes saved snapshots. Saving a board whose structure matches an existing snapshot updates that snapshot (keeping its name) rather than adding a duplicate.

**Reset board** clears every task, session and outcome while keeping the board name, the stage labels and the saved snapshots. Both reset and loading a snapshot replace the current board, so each first offers to save a snapshot of it.

### Storage

Command Deck is local-first: everything is kept in one SQLite database on your machine. The backend listens on `127.0.0.1` only.

Details (locations, overrides, runtime behaviour) are documented in [`DEVELOPMENT.md`](DEVELOPMENT.md).

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, uvicorn |
| Storage | SQLite |
| Frontend | React, TypeScript, Vite |
| Tray | pystray, Pillow, pywin32 (Windows) |
| Installer | PySide6 |
| Packaging | Nuitka |

---

## Install and run

The Windows release is a GUI installer, `CommandDeckInstaller.exe`, which installs the packaged runtime `CommandDeck.exe`; the runtime serves the UI at `http://127.0.0.1:8001/` and lives in the system tray. Running from source, with the backend and the Vite dev server, is described in [`DEVELOPMENT.md`](DEVELOPMENT.md).

---

## Tests

From the repository root, with the venv active:

```powershell
python -m pytest
```

That run is gated at 100% line and branch coverage. The other three gates (black, flake8, mypy) and how to read them are in [`TESTING.md`](TESTING.md).

---

## Build

```powershell
python buildexe.py
python buildguiinstaller.py
```

The first builds `CommandDeck.exe`; the second builds `CommandDeckInstaller.exe` around it. Prerequisites and what each bundles are in [`DEVELOPMENT.md`](DEVELOPMENT.md).

---

## Licence

Command Deck is released under the GNU General Public License v3.0; see [LICENSE](LICENSE). The installer's About dialog also shows [INSTALLER_LICENSE](INSTALLER_LICENSE), the LGPL-3.0 text covering its PySide6 interface.

A commercial licence is available for uses the GPL does not suit: see [commercial licensing](https://ernster.dev/commercial-licensing.html).
