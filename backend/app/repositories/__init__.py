"""Persistence layer (SQL only)."""

"""Persistence layer (SQL-only).

Repositories encapsulate SQLite access:

- raw SQL
- row-to-domain mapping
- basic CRUD mechanics

Rule: repositories must not contain business rules. That belongs in services.
"""
