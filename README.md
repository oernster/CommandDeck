# <img width="36" height="36" alt="CommandDeck" src="https://github.com/user-attachments/assets/256532ed-44e9-438c-9283-7c2214471155" /> Command Deck

Command Deck is a session-driven focus tool for moving **Tasks** through a fixed 4-stage workflow.

It is intentionally minimal: one board, one active session, clear stage focus.

Docs:

- Runtime design and code map: [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Developer setup / local runs / packaging: [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md)

---

## Model

Work is organised into **four fixed stages** (stable internal IDs):

`DESIGN` · `BUILD` · `REVIEW` · `COMPLETE`

The stage *labels* are renameable per board, but the number of stages and ordering remain fixed.

---

## Tasks (internal name: Commands)

In the UI we call items **Tasks**. Internally (DB/API) they are called **Commands**.

Each task belongs to a stage and progresses through a simple status model:

- Not Started
- In Progress
- Blocked
- Complete

Tasks are not plans. They are small, active units of execution.

---

## Sessions

Time is tracked at the **task level**.

Only one session can be active at a time.

Starting a session requires selecting a task; the task's stage is pinned on the session row at start.

---

## Outcomes

Outcomes record what actually happened.

They are attached to tasks/commands and form a historical trace of execution.

---

## Interface

The system is presented as a single board with four stage columns.

Global controls live in the top bar:

- **Start** (enters selection mode; click a task to begin)
- **Add** (adds a task to the focused/active stage)
- **Stop** (stops the active session)

The active stage is visually dominant; inactive stages dim slightly.

---

## Storage

Command Deck is local-first and uses a simple SQLite database for persistence.

Details (locations, overrides, runtime behavior) are documented in [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md).

---

## Philosophy

Command Deck does not optimise tasks. It exposes operational state.

It exists to answer:

- What am I doing?
- What is in motion?
- What actually happened?
