"""Call lifecycle: when a call starts and ends, and what its final status is."""

from uuid import UUID

from app.core.logging import get_logger
from app.db.unit_of_work import UnitOfWork
from app.domain.entities import CallSession, CallSummary
from app.domain.enums import CallStatus
from app.services.sessions import ensure_session

log = get_logger(__name__)


def final_status(session: CallSession) -> CallStatus:
    """A call that produced a patient is completed even if an earlier save attempt failed;
    one that failed to save is failed; anything else (hang-up before confirming) is abandoned."""
    if session.patient_id is not None:
        return CallStatus.COMPLETED
    if session.failure_reason is not None:
        return CallStatus.FAILED
    return CallStatus.ABANDONED


class CallLogService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def start(self, call_id: str, caller_number: str | None) -> CallSession:
        async with self._uow() as repos:
            session = await repos.call_sessions.start(call_id, caller_number)
        log.info("call.started", call_id=call_id, caller_last4=(caller_number or "")[-4:] or None)
        return session

    async def end(
        self,
        call_id: str,
        *,
        ended_reason: str | None = None,
        transcript: str | None = None,
        summary: str | None = None,
        recording_url: str | None = None,
        caller_number: str | None = None,
    ) -> CallSession:
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            status = final_status(session)
            ended = await repos.call_sessions.end(
                call_id,
                status,
                ended_reason=ended_reason,
                transcript=transcript,
                summary=summary,
                recording_url=recording_url,
            )
        log.info(
            "call.ended",
            call_id=call_id,
            status=status.value,
            ended_reason=ended_reason,
            patient_saved=session.patient_id is not None,
        )
        return ended or session

    async def calls_for_patient(self, patient_id: UUID) -> list[CallSummary]:
        async with self._uow(transactional=False) as repos:
            return await repos.call_sessions.list_by_patient(patient_id)
