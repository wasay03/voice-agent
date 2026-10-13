"""The registration of one patient over one phone call.

State lives in the call's `call_sessions` row (the draft), never in the LLM or in process memory:
a correction, a restart or a server restart mid-call are all plain operations on that row. Every
mutating operation locks the row first, so tool calls the model emits in parallel are applied one
at a time.

Two rules carry the design:
* Submit succeeds only if the draft is still at the version that was read back, so what the
  caller confirmed is exactly what gets saved.
* Submit is idempotent per call: a retry returns `already_saved` instead of a second patient.

Business logic only. Spoken wording is rendered by the caller (app/agent) and passed in.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.core.errors import DataIntegrityError
from app.core.logging import get_logger
from app.db.unit_of_work import Repositories, UnitOfWork
from app.domain.clock import clinic_today
from app.domain.entities import CallSession, DuplicateCandidate, ReadbackChunk
from app.domain.enums import RegistrationMode, SubmitStatus
from app.domain.fields import ALL_FIELDS, OPTIONAL_FIELDS, REQUIRED_FIELDS
from app.domain.schemas import PatientCreate, PatientOut, PatientUpdate
from app.domain.validators import FieldError, validate_fields
from app.services.sessions import ensure_session
from app.utils.phone import is_valid_nanp, to_10_digits
from app.utils.timeouts import run_with_timeout

log = get_logger(__name__)

CALLER_ID_SENTINEL = "CALLER_ID"

# draft -> language code ("en", "es") -> spoken chunks. Injected so this layer stays speech-free.
ReadbackRenderer = Callable[[dict[str, Any], str], list[ReadbackChunk]]


@dataclass
class SaveFieldsResult:
    saved: list[str] = field(default_factory=list)
    errors: list[FieldError] = field(default_factory=list)
    next_missing: list[str] = field(default_factory=list)
    existing_patients: list[DuplicateCandidate] = field(default_factory=list)
    draft_version: int = 0
    mode: RegistrationMode = RegistrationMode.CREATE


@dataclass
class ReadbackResult:
    ready: bool
    missing: list[str] = field(default_factory=list)
    chunks: list[ReadbackChunk] = field(default_factory=list)
    delivering: ReadbackChunk | None = None  # the chunk to read aloud now
    remaining_keys: list[str] = field(default_factory=list)  # still to read after that one
    readback_version: int | None = None


@dataclass
class ReadbackPart:
    chunk: ReadbackChunk
    remaining_keys: list[str] = field(default_factory=list)


@dataclass
class SubmitResult:
    status: SubmitStatus
    patient: PatientOut | None = None
    mode: RegistrationMode = RegistrationMode.CREATE
    errors: list[FieldError] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unread_parts: list[str] = field(default_factory=list)
    retryable: bool = False


@dataclass
class SwitchResult:
    switched: bool
    draft: dict[str, Any] = field(default_factory=dict)
    next_missing: list[str] = field(default_factory=list)
    draft_version: int = 0


@dataclass
class ResetResult:
    cleared: bool
    draft_version: int = 0


def to_json_value(value: Any) -> Any:
    """Draft values are stored JSON-ready: dates as ISO strings, enums as their value."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def caller_digits(caller_number: str | None) -> str | None:
    """The caller's number as 10 NANP digits, or None if blocked or not a US number."""
    if not caller_number:
        return None
    digits = to_10_digits(caller_number)
    return digits if is_valid_nanp(digits) else None


def missing_required(draft: dict[str, Any]) -> list[str]:
    return [f.value for f in REQUIRED_FIELDS if draft.get(f.value) in (None, "")]


def _errors_from_validation(exc: ValidationError) -> list[FieldError]:
    return [
        FieldError(
            str(e["loc"][0]) if e["loc"] else "*", e["type"], str(e["msg"]).removeprefix("Value error, ")
        )
        for e in exc.errors()
    ]


def _closed_error() -> FieldError:
    return FieldError("*", "already_submitted", "This registration was already saved on this call.")


class RegistrationService:
    def __init__(self, uow: UnitOfWork, *, tool_timeout_seconds: float = 4.0) -> None:
        self._uow = uow
        self._timeout = tool_timeout_seconds

    # -- collecting ------------------------------------------------------------------------

    async def save_fields(
        self, call_id: str, fields: dict[str, Any], *, caller_number: str | None = None
    ) -> SaveFieldsResult:
        """Validate each field on its own and merge the good ones into the draft.

        One bad field never discards the others from the same call. Empty optional values clear
        the field. The draft version only moves when the draft actually changed.
        """
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            if session.is_submitted:
                return SaveFieldsResult(
                    errors=[_closed_error()], draft_version=session.draft_version, mode=session.mode
                )

            data = dict(fields)
            errors: list[FieldError] = []
            phone = data.get("phone_number")
            if isinstance(phone, str) and phone.strip().upper() == CALLER_ID_SENTINEL:
                digits = caller_digits(session.caller_number)
                if digits:
                    data["phone_number"] = digits
                else:
                    del data["phone_number"]
                    # A blocked number and a non-US number need different words: telling a caller
                    # from abroad "I don't see a number" is simply wrong.
                    errors.append(
                        FieldError(
                            "phone_number", "caller_id_not_us", "The caller's number is not a US number."
                        )
                        if session.caller_number
                        else FieldError("phone_number", "caller_id_unavailable", "No caller ID on this call.")
                    )

            outcome = validate_fields(data, today=clinic_today())
            errors += outcome.errors

            draft = dict(session.draft)
            for name, value in outcome.values.items():
                if value is None:
                    draft.pop(name, None)
                else:
                    draft[name] = to_json_value(value)

            version = session.draft_version
            if draft != session.draft:
                version = await repos.call_sessions.save_draft(call_id, draft)

            phone_changed = draft.get("phone_number") != session.draft.get("phone_number")
            existing: list[DuplicateCandidate] = []
            if phone_changed and "phone_number" in draft and session.mode is RegistrationMode.CREATE:
                existing = await repos.patients.find_by_phone(draft["phone_number"])

        return SaveFieldsResult(
            saved=list(outcome.values),
            errors=errors,
            next_missing=missing_required(draft),
            existing_patients=existing,
            draft_version=version,
            mode=session.mode,
        )

    # -- confirming ------------------------------------------------------------------------

    async def get_readback(
        self,
        call_id: str,
        render: ReadbackRenderer,
        *,
        language: str = "en",
        caller_number: str | None = None,
    ) -> ReadbackResult:
        """Render the draft for the ear, remember it, and hand out the first chunk to read aloud.

        A chunk counts as delivered once it has been handed out with its current text. Chunks
        delivered earlier and untouched by a correction are not repeated; submit is refused until
        every chunk has been delivered, so no detail is saved without having been read back.
        """
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            missing = missing_required(session.draft)
            if missing:
                return ReadbackResult(ready=False, missing=missing)

            chunks = render(session.draft, language)
            previous = {c.get("key"): c for c in (session.readback_chunks or [])}
            for chunk in chunks:
                old = previous.get(chunk.key)
                chunk.delivered = bool(old and old.get("text") == chunk.text and old.get("delivered"))
            pending = [c for c in chunks if not c.delivered]
            if not pending:  # asked again with nothing new: read everything from the start
                for chunk in chunks:
                    chunk.delivered = False
                pending = list(chunks)
            delivering = pending[0]
            delivering.delivered = True
            await repos.call_sessions.save_readback(call_id, session.draft_version, chunks)

        return ReadbackResult(
            ready=True,
            chunks=chunks,
            delivering=delivering,
            remaining_keys=[c.key for c in pending[1:]],
            readback_version=session.draft_version,
        )

    async def readback_part(
        self, call_id: str, key: str, *, caller_number: str | None = None
    ) -> ReadbackPart | None:
        """Hand out one more chunk of the stored readback and mark it delivered.

        None if there is no current readback (the draft changed since, or `key` is unknown), in
        which case get_readback must be called again.
        """
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            if session.readback_version is None or session.readback_version != session.draft_version:
                return None
            chunks = [ReadbackChunk.model_validate(raw) for raw in session.readback_chunks or []]
            chunk = next((c for c in chunks if c.key == key), None)
            if chunk is None:
                return None
            chunk.delivered = True
            await repos.call_sessions.save_readback(call_id, session.readback_version, chunks)
        return ReadbackPart(chunk=chunk, remaining_keys=[c.key for c in chunks if not c.delivered])

    # -- saving ----------------------------------------------------------------------------

    async def submit(
        self, call_id: str, readback_version: int, *, caller_number: str | None = None
    ) -> SubmitResult:
        """Write the confirmed draft once. Never raises: every failure is a result the agent can speak."""
        try:
            return await run_with_timeout(
                self._submit(call_id, readback_version, caller_number), self._timeout
            )
        except DataIntegrityError as exc:
            log.error(
                "registration.rejected", call_id=call_id, constraint=exc.constraint, message=exc.message
            )
            await self._record_failure(call_id, f"rejected: {exc.constraint or exc.message}")
            return SubmitResult(
                SubmitStatus.INVALID,
                errors=[FieldError(exc.column or "*", exc.constraint or "constraint", exc.message)],
            )
        except Exception as exc:  # database down, timeout, anything else: the caller must hear an outcome
            log.error("registration.failed", call_id=call_id, error=type(exc).__name__, detail=str(exc))
            repeated = await self._record_failure(call_id, f"{type(exc).__name__}: {exc}")
            # One retry is worth it; after a second failure the caller should be let go politely.
            return SubmitResult(SubmitStatus.ERROR, retryable=not repeated)

    async def _submit(self, call_id: str, readback_version: int, caller_number: str | None) -> SubmitResult:
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)

            if session.patient_id is not None:  # retry after a success, or a redelivered webhook
                patient = await repos.patients.get_by_id(session.patient_id)
                return SubmitResult(SubmitStatus.ALREADY_SAVED, patient=patient, mode=session.mode)

            if readback_version != session.readback_version or readback_version != session.draft_version:
                return SubmitResult(SubmitStatus.STALE_READBACK, mode=session.mode)

            unread = [c["key"] for c in session.readback_chunks or [] if not c.get("delivered")]
            if unread:  # the model tried to save before every part was read to the caller
                return SubmitResult(SubmitStatus.READBACK_INCOMPLETE, mode=session.mode, unread_parts=unread)

            missing = missing_required(session.draft)
            if missing:
                return SubmitResult(SubmitStatus.INVALID, mode=session.mode, missing=missing)

            if session.mode is RegistrationMode.UPDATE:
                result = await self._apply_update(repos, session)
            else:
                result = await self._apply_create(repos, session)
            if result.patient is None:
                return result
            await repos.call_sessions.link_patient(call_id, result.patient.patient_id)

        log.info(
            "registration.submitted",
            call_id=call_id,
            patient_id=str(result.patient.patient_id),
            mode=session.mode.value,
            payload=session.draft,
        )
        return result

    @staticmethod
    async def _apply_create(repos: Repositories, session: CallSession) -> SubmitResult:
        try:
            payload = PatientCreate.model_validate(session.draft)
        except ValidationError as exc:
            return SubmitResult(SubmitStatus.INVALID, errors=_errors_from_validation(exc))
        patient = await repos.patients.create(payload)
        return SubmitResult(SubmitStatus.CREATED, patient=patient, mode=RegistrationMode.CREATE)

    @staticmethod
    async def _apply_update(repos: Repositories, session: CallSession) -> SubmitResult:
        assert session.target_patient_id is not None  # guaranteed by call_sessions_update_has_target
        existing = await repos.patients.get_by_id(session.target_patient_id)
        if existing is None:
            return SubmitResult(
                SubmitStatus.INVALID,
                mode=RegistrationMode.UPDATE,
                errors=[FieldError("*", "patient_missing", "The existing record is no longer available.")],
            )
        changes: dict[str, Any] = {}
        for name, value in session.draft.items():
            if to_json_value(getattr(existing, name, None)) != value:
                changes[name] = value
        for f in OPTIONAL_FIELDS:  # optional fields the caller removed
            if f.value not in session.draft and getattr(existing, f.value, None) is not None:
                changes[f.value] = None
        if not changes:  # nothing differs from the record: confirm without touching it
            return SubmitResult(SubmitStatus.UPDATED, patient=existing, mode=RegistrationMode.UPDATE)
        try:
            update = PatientUpdate.model_validate(changes)
        except ValidationError as exc:
            return SubmitResult(
                SubmitStatus.INVALID, mode=RegistrationMode.UPDATE, errors=_errors_from_validation(exc)
            )
        patient = await repos.patients.update(existing.patient_id, update.changes())
        if patient is None:
            return SubmitResult(SubmitStatus.ERROR, mode=RegistrationMode.UPDATE, retryable=True)
        return SubmitResult(SubmitStatus.UPDATED, patient=patient, mode=RegistrationMode.UPDATE)

    async def _record_failure(self, call_id: str, reason: str) -> bool:
        """Mark the session failed, in a fresh transaction (the failed one has rolled back).

        Returns True if an earlier save attempt on this call had already failed. Best effort: if
        even this cannot be written, the error log line is the record.
        """
        try:
            async with self._uow() as repos:
                session = await repos.call_sessions.lock(call_id)
                repeated = session is not None and session.failure_reason is not None
                await repos.call_sessions.mark_failed(call_id, reason[:500])
            return repeated
        except Exception as exc:
            log.error("registration.failure_not_recorded", call_id=call_id, error=type(exc).__name__)
            return False

    # -- duplicates and restarts -----------------------------------------------------------

    async def switch_to_update(
        self, call_id: str, patient_id: UUID, *, caller_number: str | None = None
    ) -> SwitchResult:
        """Load an existing patient into the draft, so the call updates that record.

        Only a patient who shares the phone number already in the draft can be chosen, so a
        caller (or a confused model) cannot pull up arbitrary records by id.
        """
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            phone = session.draft.get("phone_number")
            if session.is_submitted or not phone:
                return SwitchResult(switched=False, draft_version=session.draft_version)
            candidates = await repos.patients.find_by_phone(phone)
            if patient_id not in {c.patient_id for c in candidates}:
                return SwitchResult(switched=False, draft_version=session.draft_version)
            existing = await repos.patients.get_by_id(patient_id)
            if existing is None:
                return SwitchResult(switched=False, draft_version=session.draft_version)

            record = {
                name: to_json_value(getattr(existing, name))
                for name in ALL_FIELDS
                if getattr(existing, name, None) is not None
            }
            draft = {**record, **session.draft}  # what the caller said on this call wins
            version = await repos.call_sessions.switch_mode(
                call_id, RegistrationMode.UPDATE, patient_id, draft
            )
        return SwitchResult(
            switched=True, draft=draft, next_missing=missing_required(draft), draft_version=version
        )

    async def reset(self, call_id: str, *, caller_number: str | None = None) -> ResetResult:
        """Start over. Refused once the registration has been saved (the record exists)."""
        async with self._uow() as repos:
            session = await ensure_session(repos, call_id, caller_number)
            if session.is_submitted:
                return ResetResult(cleared=False, draft_version=session.draft_version)
            version = await repos.call_sessions.reset(call_id)
        return ResetResult(cleared=True, draft_version=version)
