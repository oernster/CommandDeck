from __future__ import annotations

from app.tray.runtime import run_tray


def main() -> None:
    run_tray()


def _coverage_entrypoint() -> None:
    """Hook for unit tests to cover the module without launching a real tray."""
    main()


if __name__ == "__main__":
    main()
