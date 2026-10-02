# Testing

How Command Deck is tested: the quality gates, reading what they say, what the
suite holds and leaves out; how a new test is written. The code map is in
[ARCHITECTURE.md](ARCHITECTURE.md); setting up the environment the gates run in
is in [DEVELOPMENT.md](DEVELOPMENT.md).

## Running the gates

From the repository root, with the venv active:

```powershell
python -m black --check backend
python -m flake8 backend
python -m mypy backend/app
python -m pytest
```

`pytest` alone is the coverage-gated run: the options in `pyproject.toml` add
the coverage measurement over the backend application and the 100% floor, by
line AND branch. mypy runs in strict mode, set in `pyproject.toml`. There is no
CI, so run all four and read the exit code of each.

**A full run takes about twenty seconds.** Measured on 2026-10-02: 180 tests
passed in 22 seconds on Windows.

**Read the exit code, never the text.** The run prints the coverage table then
one summary line. That line reads "passed" even when the coverage floor
has failed the run. `0` means the tests passed AND the floor was met.

## The gate does not currently pass

Measured on 2026-10-02, before any change to the backend:

| Gate | State |
|---|---|
| black | passes |
| flake8 | 5 lines over 88 columns, all long SQL strings in `backend/tests/test_database.py` and `backend/tests/test_snapshots.py` |
| mypy | 20 errors in 8 files; 9 are redundant casts in `backend/app/api/snapshots.py`, the rest missing or invalid annotations |
| pytest | all 180 tests pass; coverage is 99.94%, one branch short: `backend/app/services/snapshot_service.py` line 256 to 266 is never taken |

So `pytest` exits non-zero on the floor alone, as do flake8 and mypy. A result
from any of the four is only news when it differs from this table.

## What the suite holds and leaves out

The backend tests are full stack: API, services, repositories and a real
SQLite database. `backend/tests/conftest.py` makes a fresh temporary database
file for every test and swaps the application's database dependency for it
through FastAPI's `dependency_overrides`, so requests made through the
`TestClient` reach that file and nothing else.

- **Your database is never written.** A run from source keeps its database at
  `%LOCALAPPDATA%\CommandDeck\command_deck.db`; measured on 2026-10-02, a full
  run left it untouched.
- **The frontend has no tests.** `frontend/` carries a lint script
  (`npm run lint`, eslint) and the TypeScript compile that `npm run build`
  runs; no test runner.
- **The build scripts are not tested.** `buildexe.py`, `buildguiinstaller.py`
  and `buildicon.py` sit outside the coverage source, which is the backend
  application alone.

## Where the tests live

All files sit flat in `backend/tests/`:

| Files | What they hold |
|---|---|
| `test_commands.py`, `test_sessions.py`, `test_snapshots.py`, `test_outcomes*.py`, `test_board_reset.py`, `test_health.py` | the API end to end through the `TestClient` |
| `test_database.py` | the schema and the repositories against SQLite directly |
| `test_static_serving.py` | serving the production frontend build from the backend |
| `test_runtime_paths.py`, `test_tray_runtime.py` | where the packaged runtime keeps its files; the tray |
| `test_installer_uninstall_preserves_db.py` | the installer keeping the database on uninstall |
| `test_coverage_edges.py` | the repositories and services driven directly rather than through the API |

## Writing a test

- **Go through the API where you can.** Take the `client` fixture from
  `conftest.py`, a `TestClient` over the application; the request then runs
  through every layer against the test's own database file.
- **Real SQLite, not fakes.** Ask for `db_connection` when a test needs the
  database directly; it is a real connection to the per-test file with foreign
  keys on.
- **No mocking library.** Replace a dependency through
  `app.dependency_overrides` or pytest's `monkeypatch`.

---

See also [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md) and
[DEVELOPMENT.md](DEVELOPMENT.md).
