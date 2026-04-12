"""Single source of truth for Command Deck version.

This module is used by:
- the backend (FastAPI app metadata)
- the GUI installer (VERSION file generation)

Keep this version in sync with the top-level VERSION file created by
`buildguiinstaller.py`.
"""

VERSION = "1.0.0"
