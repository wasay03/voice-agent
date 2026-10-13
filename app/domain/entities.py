"""Internal records that are not part of the public API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.enums import CallStatus, RegistrationMode


class CallSession(BaseModel):
    """One phone call: the registration draft while it is live, then its outcome (call_sessions row)."""

    call_id: str
    caller_number: str | None = None
    status: CallStatus = CallStatus.IN_PROGRESS
    mode: RegistrationMode = RegistrationMode.CREATE
    target_patient_id: UUID | None = None
    draft: dict[str, Any] = Field(default_factory=dict)
    draft_version: int = 0
    readback_version: int | None = None
    readback_chunks: list[dict[str, Any]] | None = None
    patient_id: UUID | None = None
    failure_reason: str | None = None
    ended_reason: str | None = None
    transcript: str | None = None
    summary: str | None = None
    recording_url: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    ended_at: datetime | None = None

    @property
    def is_submitted(self) -> bool:
        return self.patient_id is not None


class DuplicateCandidate(BaseModel):
    """An existing patient sharing the caller's phone number (duplicate detection)."""

    patient_id: UUID
    first_name: str
    last_name: str
