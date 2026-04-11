"""Windows-only local runtime (system tray) for Command Deck.

This package provides a minimal tray process that:

- starts the backend server (uvicorn)
- offers menu actions (open browser / quit)

It is kept separate from the web app code to preserve layering and avoid importing
GUI dependencies in normal backend operation.
"""

__all__: tuple[str, ...] = ()
