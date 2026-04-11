from __future__ import annotations


class ValidationError(ValueError):
    """Raised when input is invalid according to v1 rules."""


class NotFoundError(LookupError):
    """Raised when a requested entity does not exist."""
