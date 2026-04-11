"""Command Deck backend package.

This file exists primarily to:

- mark `backend/app` as a Python package for imports like `app.main:app`
- document the top-level boundary of the backend code (FastAPI + domain/services/repos)

v1 intentionally keeps package exports implicit to avoid cross-layer coupling.
"""

# This module intentionally does not re-export subpackages.
# Keeping a real statement here avoids "empty file" skips in coverage reporting.
__all__: tuple[str, ...] = ()
