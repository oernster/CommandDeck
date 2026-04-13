from __future__ import annotations

from enum import Enum


class StageId(str, Enum):
    """Stable internal identifiers for the fixed 4-stage workflow.

    These values are persisted in SQLite and used in the HTTP API. The user can
    rename *labels* per board, but the number of stages and ordering remain fixed.
    """

    DESIGN = "DESIGN"
    BUILD = "BUILD"
    REVIEW = "REVIEW"
    COMPLETE = "COMPLETE"

    @classmethod
    def from_str(cls, value: str) -> "StageId | None":
        # Backwards-compatible parsing: older clients / data may still use the
        # v1 display labels ("Design", ...). We accept those as aliases and
        # normalize to stable IDs.
        aliases = {
            "Design": cls.DESIGN,
            "Build": cls.BUILD,
            "Review": cls.REVIEW,
            "Complete": cls.COMPLETE,
            # v1 legacy categories; safest default mapping is to treat them as
            # "Complete" when encountered during upgrades.
            "Maintain": cls.COMPLETE,
            "Recover": cls.COMPLETE,
        }
        if value in aliases:
            return aliases[value]

        for member in cls:
            if member.value == value:
                return member
        return None


class Status(str, Enum):
    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    BLOCKED = "Blocked"
    COMPLETE = "Complete"

    @classmethod
    def from_str(cls, value: str) -> "Status | None":
        for member in cls:
            if member.value == value:
                return member
        return None
