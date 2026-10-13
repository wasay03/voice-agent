"""Data access for call sessions: one routine per method."""

from typing import Any
from uuid import UUID

from app.db.repositories.base import BaseRepository
from app.domain.entities import CallSession, CallSummary, ReadbackChunk
from app.domain.enums import CallStatus, RegistrationMode


def _to_session(record: dict[str, Any] | None) -> CallSession | None:
    return CallSession.model_validate(record) if record is not None else None


class CallSessionRepository(BaseRepository):
    async def get(self, call_id: str) -> CallSession | None:
        return _to_session(await self._fn_value("fn_call_session_get", call_id))

    async def lock(self, call_id: str) -> CallSession | None:
        """Read with a row lock; only meaningful inside a unit of work."""
        return _to_session(await self._fn_value("fn_call_session_lock", call_id))

    async def start(self, call_id: str, caller_number: str | None) -> CallSession:
        row = await self._sp("sp_call_session_start", call_id, caller_number, outputs=("jsonb",))
        session = _to_session(row["p_record"] if row else None)
        if session is None:
            raise RuntimeError("sp_call_session_start returned no record")
        return session

    async def save_draft(self, call_id: str, draft: dict[str, Any]) -> int:
        row = await self._sp("sp_call_session_save_draft", call_id, draft, outputs=("integer",))
        return self._version(row, "sp_call_session_save_draft")

    async def save_readback(self, call_id: str, version: int, chunks: list[ReadbackChunk]) -> None:
        await self._sp("sp_call_session_save_readback", call_id, version, [c.model_dump() for c in chunks])

    async def switch_mode(
        self, call_id: str, mode: RegistrationMode, target_patient_id: UUID | None, draft: dict[str, Any]
    ) -> int:
        row = await self._sp(
            "sp_call_session_switch_mode", call_id, mode.value, target_patient_id, draft, outputs=("integer",)
        )
        return self._version(row, "sp_call_session_switch_mode")

    async def reset(self, call_id: str) -> int:
        row = await self._sp("sp_call_session_reset", call_id, outputs=("integer",))
        return self._version(row, "sp_call_session_reset")

    async def link_patient(self, call_id: str, patient_id: UUID) -> None:
        await self._sp("sp_call_session_link_patient", call_id, patient_id)

    async def mark_failed(self, call_id: str, reason: str) -> None:
        await self._sp("sp_call_session_mark_failed", call_id, reason)

    async def end(
        self,
        call_id: str,
        status: CallStatus,
        *,
        ended_reason: str | None,
        transcript: str | None,
        summary: str | None,
        recording_url: str | None,
    ) -> CallSession | None:
        row = await self._sp(
            "sp_call_session_end",
            call_id,
            status.value,
            ended_reason,
            transcript,
            summary,
            recording_url,
            outputs=("jsonb",),
        )
        return _to_session(row["p_record"] if row else None)

    async def list_by_patient(self, patient_id: UUID) -> list[CallSummary]:
        rows = await self._fn_rows("fn_call_session_list_by_patient", patient_id)
        return [CallSummary.model_validate(dict(r)) for r in rows]

    @staticmethod
    def _version(row: Any, routine: str) -> int:
        version = row["p_draft_version"] if row else None
        if version is None:  # the UPDATE matched no session
            raise RuntimeError(f"{routine}: call session does not exist")
        return int(version)
