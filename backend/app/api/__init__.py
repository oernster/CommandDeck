"""FastAPI routers (HTTP layer only).

Routers in this package:

- define endpoints and request/response schemas
- parse/validate user input into domain types
- delegate behavior to services

They must not:

- execute SQL
- implement business rules
"""

__all__: tuple[str, ...] = ()
