"""Infrastructure wiring (config, database, lifecycle).

This package contains runtime concerns that sit *under* the domain and services:

- configuration defaults
- SQLite connection helpers + schema initialization
- startup lifecycle wiring

Keeping these in `core/` helps preserve strict layering.
"""

__all__: tuple[str, ...] = ()
