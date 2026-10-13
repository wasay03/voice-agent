"""Enumerations shared by the API, the voice tools and the database (values match sql/types/)."""

from enum import StrEnum


class Sex(StrEnum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE = "Decline to Answer"


class CallStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    FAILED = "failed"


class RegistrationMode(StrEnum):
    CREATE = "create"
    UPDATE = "update"


class SubmitStatus(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    ALREADY_SAVED = "already_saved"
    STALE_READBACK = "stale_readback"
    INVALID = "invalid"
    ERROR = "error"
