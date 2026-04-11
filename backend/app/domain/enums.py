from __future__ import annotations

from enum import Enum


class Category(str, Enum):
    DESIGN = "Design"
    BUILD = "Build"
    REVIEW = "Review"
    MAINTAIN = "Maintain"
    RECOVER = "Recover"

    @classmethod
    def from_str(cls, value: str) -> "Category | None":
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
