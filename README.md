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

- 🔴 Blocked
- 🟠 In Progress
- 🟢 Complete
- ⚪ Not Started

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

The system is intentionally minimal.
