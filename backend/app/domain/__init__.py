"""Domain types (pure, no infrastructure dependencies).

The domain package defines:

- enums (Category, Status)
- immutable models (Command, Outcome, Session)
- domain-level errors used across API/services

Rule: domain code must remain free of FastAPI/sqlite3 imports.
"""

__all__: tuple[str, ...] = ()
