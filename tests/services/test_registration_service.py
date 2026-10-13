"""The registration flow against a real database: the behaviours the brief's reviewers will probe."""

import asyncio
import uuid
from typing import Any

import pytest

from app.agent.speech.readback import IDENTITY_CONTACT, render_readback
from app.core.errors import DatabaseUnavailableError
from app.db.repositories.patient_repository import PatientRepository
from app.db.unit_of_work import UnitOfWork
from app.domain.enums import CallStatus, RegistrationMode, SubmitStatus
from app.services.call_log_service import CallLogService
from app.services.registration_service import RegistrationService
from tests.conftest import new_call_id, unique_phone


@pytest.fixture
def registration(uow: UnitOfWork) -> RegistrationService:
    return RegistrationService(uow, tool_timeout_seconds=4)


@pytest.fixture
def calls(uow: UnitOfWork) -> CallLogService:
    return CallLogService(uow)


def full_draft(**overrides: Any) -> dict[str, Any]:
    return {
        "first_name": "jane",
        "last_name": "Davies",
        "date_of_birth": "1980-03-05",
        "sex": "female",
        "phone_number": unique_phone(),
        "address_line_1": "1200 Barton Springs Rd",
        "city": "austin",
        "state": "texas",
        "zip_code": "78704",
        **overrides,
    }


async def confirmed_submit(service: RegistrationService, call_id: str):
    readback = await service.get_readback(call_id, render_readback)
    assert readback.ready, readback.missing
    assert readback.readback_version is not None
    return await service.submit(call_id, readback.readback_version)


async def test_answers_in_any_order_and_next_missing_tracks_progress(
    registration: RegistrationService,
) -> None:
    call_id = new_call_id()
    first = await registration.save_fields(
        call_id, {"first_name": "Jane", "last_name": "Doe", "date_of_birth": "1980-03-05", "city": "Austin"}
    )
    assert first.saved == ["first_name", "last_name", "date_of_birth", "city"]
    assert first.errors == []
    assert first.next_missing == ["sex", "phone_number", "address_line_1", "state", "zip_code"]

    second = await registration.save_fields(call_id, {"zip_code": "78704", "state": "texas"})
    assert second.next_missing == ["sex", "phone_number", "address_line_1"]
    assert second.draft_version > first.draft_version


async def test_one_bad_field_does_not_discard_the_others(registration: RegistrationService) -> None:
    result = await registration.save_fields(
        new_call_id(), {"first_name": "Jane", "date_of_birth": "2999-01-01", "zip_code": "78704"}
    )
    assert result.saved == ["first_name", "zip_code"]
    assert [(e.field, e.code) for e in result.errors] == [("date_of_birth", "dob_future")]
    assert "date_of_birth" in result.next_missing


async def test_nine_digit_phone_is_rejected_with_the_count(registration: RegistrationService) -> None:
    result = await registration.save_fields(new_call_id(), {"phone_number": "512555019"})
    assert result.saved == []
    assert result.errors[0].code == "phone_length"
    assert result.errors[0].params == {"digit_count": 9}


async def test_unchanged_save_does_not_bump_the_version(registration: RegistrationService) -> None:
    call_id = new_call_id()
    first = await registration.save_fields(call_id, {"first_name": "Jane"})
    again = await registration.save_fields(call_id, {"first_name": "jane"})  # normalises to the same value
    assert again.draft_version == first.draft_version


async def test_happy_path_creates_one_normalised_patient(
    registration: RegistrationService, uow: UnitOfWork
) -> None:
    call_id = new_call_id()
    draft = full_draft()
    await registration.save_fields(call_id, draft)

    result = await confirmed_submit(registration, call_id)

    assert result.status is SubmitStatus.CREATED
    assert result.patient is not None
    assert (result.patient.first_name, result.patient.city, result.patient.state) == ("Jane", "Austin", "TX")
    async with uow(transactional=False) as repos:
        session = await repos.call_sessions.get(call_id)
        assert session is not None and session.patient_id == result.patient.patient_id


async def test_correction_after_readback_forces_a_new_readback_of_the_changed_chunk(
    registration: RegistrationService,
) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, full_draft(last_name="Davies"))
    first = await registration.get_readback(call_id, render_readback)
    assert first.ready and first.changed_keys == ["identity_contact", "address_extras"]

    await registration.save_fields(call_id, {"last_name": "Davis"})  # "it's D-A-V-I-S, not D-A-V-I-E-S"

    stale = await registration.submit(call_id, first.readback_version)  # type: ignore[arg-type]
    assert stale.status is SubmitStatus.STALE_READBACK
    assert stale.patient is None

    second = await registration.get_readback(call_id, render_readback)
    assert second.changed_keys == [IDENTITY_CONTACT]  # only the name chunk is re-read
    assert "D-A-V-I-S" in second.chunks[0].text
    assert second.readback_version != first.readback_version

    done = await registration.submit(call_id, second.readback_version)  # type: ignore[arg-type]
    assert done.status is SubmitStatus.CREATED
    assert done.patient is not None and done.patient.last_name == "Davis"


async def test_submit_without_a_readback_is_refused(registration: RegistrationService) -> None:
    call_id = new_call_id()
    saved = await registration.save_fields(call_id, full_draft())
    result = await registration.submit(call_id, saved.draft_version)
    assert result.status is SubmitStatus.STALE_READBACK


async def test_readback_lists_what_is_missing(registration: RegistrationService) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, {"first_name": "Jane"})
    readback = await registration.get_readback(call_id, render_readback)
    assert not readback.ready
    assert "last_name" in readback.missing and readback.chunks == []


async def test_double_submit_is_idempotent(registration: RegistrationService, uow: UnitOfWork) -> None:
    call_id = new_call_id()
    draft = full_draft()
    await registration.save_fields(call_id, draft)
    readback = await registration.get_readback(call_id, render_readback)
    version = readback.readback_version
    assert version is not None

    first = await registration.submit(call_id, version)
    again = await registration.submit(call_id, version)  # the model retries, or the webhook is redelivered

    assert first.status is SubmitStatus.CREATED
    assert again.status is SubmitStatus.ALREADY_SAVED
    assert again.patient is not None and first.patient is not None
    assert again.patient.patient_id == first.patient.patient_id
    async with uow(transactional=False) as repos:
        assert len(await repos.patients.find_by_phone(first.patient.phone_number)) == 1


async def test_concurrent_saves_are_serialised_not_lost(registration: RegistrationService) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, {"first_name": "Jane"})
    await asyncio.gather(
        registration.save_fields(call_id, {"last_name": "Doe"}),
        registration.save_fields(call_id, {"city": "Austin"}),
        registration.save_fields(call_id, {"zip_code": "78704"}),
    )
    final = await registration.save_fields(call_id, {})
    assert final.next_missing == ["date_of_birth", "sex", "phone_number", "address_line_1", "state"]


async def test_database_failure_returns_a_retryable_error_then_recovers(
    registration: RegistrationService, calls: CallLogService, uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, full_draft())
    readback = await registration.get_readback(call_id, render_readback)
    version = readback.readback_version
    assert version is not None

    with monkeypatch.context() as patch:

        async def broken(self: PatientRepository, *_: Any, **__: Any) -> Any:
            raise DatabaseUnavailableError()

        patch.setattr(PatientRepository, "create", broken)
        failed = await registration.submit(call_id, version)

    assert failed.status is SubmitStatus.ERROR
    assert failed.retryable
    async with uow(transactional=False) as repos:
        session = await repos.call_sessions.get(call_id)
        assert session is not None
        assert session.status is CallStatus.FAILED and session.patient_id is None
        assert session.failure_reason and "DatabaseUnavailableError" in session.failure_reason
        assert session.draft  # nothing the caller said was lost

    retried = await registration.submit(call_id, version)  # the agent's one retry
    assert retried.status is SubmitStatus.CREATED

    ended = await calls.end(call_id, ended_reason="customer-ended-call")
    assert ended.status is CallStatus.COMPLETED  # an earlier failure does not mask the success


async def test_slow_save_times_out_with_an_error_not_silence(
    uow: UnitOfWork, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = RegistrationService(uow, tool_timeout_seconds=0.3)
    call_id = new_call_id()
    await service.save_fields(call_id, full_draft())
    readback = await service.get_readback(call_id, render_readback)

    async def stalled(self: PatientRepository, *_: Any, **__: Any) -> Any:
        await asyncio.sleep(5)

    monkeypatch.setattr(PatientRepository, "create", stalled)
    result = await service.submit(call_id, readback.readback_version)  # type: ignore[arg-type]
    assert result.status is SubmitStatus.ERROR and result.retryable


async def test_caller_id_shortcut_uses_the_number_on_the_call(registration: RegistrationService) -> None:
    result = await registration.save_fields(
        new_call_id(), {"phone_number": "CALLER_ID"}, caller_number="+15125550123"
    )
    assert result.saved == ["phone_number"] and result.errors == []

    blocked = await registration.save_fields(new_call_id(), {"phone_number": "CALLER_ID"})
    assert blocked.saved == []
    assert blocked.errors[0].code == "caller_id_unavailable"


async def test_returning_caller_is_offered_the_existing_record_and_can_update_it(
    registration: RegistrationService, uow: UnitOfWork
) -> None:
    phone = unique_phone()
    first_call = new_call_id()
    await registration.save_fields(first_call, full_draft(phone_number=phone, city="Austin"))
    original = await confirmed_submit(registration, first_call)
    assert original.patient is not None

    second_call = new_call_id()
    saved = await registration.save_fields(second_call, {"first_name": "Jane", "phone_number": phone})
    assert [(p.first_name, p.last_name) for p in saved.existing_patients] == [("Jane", "Davies")]

    refused = await registration.switch_to_update(second_call, uuid.UUID(int=1))
    assert not refused.switched  # not one of the matches for this phone number

    switched = await registration.switch_to_update(second_call, saved.existing_patients[0].patient_id)
    assert switched.switched and switched.next_missing == []  # the record filled every required field
    assert switched.draft["last_name"] == "Davies"

    await registration.save_fields(second_call, {"city": "Dallas", "address_line_1": "9 Elm St"})
    updated = await confirmed_submit(registration, second_call)

    assert updated.status is SubmitStatus.UPDATED and updated.mode is RegistrationMode.UPDATE
    assert updated.patient is not None
    assert updated.patient.patient_id == original.patient.patient_id  # same record, no duplicate
    assert (updated.patient.city, updated.patient.address_line_1) == ("Dallas", "9 Elm St")
    async with uow(transactional=False) as repos:
        assert len(await repos.patients.find_by_phone(phone)) == 1


async def test_update_with_nothing_changed_confirms_without_writing(
    registration: RegistrationService,
) -> None:
    phone = unique_phone()
    call_one, call_two = new_call_id(), new_call_id()
    await registration.save_fields(call_one, full_draft(phone_number=phone))
    original = await confirmed_submit(registration, call_one)
    assert original.patient is not None

    saved = await registration.save_fields(call_two, {"phone_number": phone})
    await registration.switch_to_update(call_two, saved.existing_patients[0].patient_id)
    result = await confirmed_submit(registration, call_two)
    assert result.status is SubmitStatus.UPDATED
    assert result.patient is not None and result.patient.updated_at == original.patient.updated_at


async def test_start_over_clears_the_draft_and_invalidates_the_readback(
    registration: RegistrationService,
) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, full_draft())
    readback = await registration.get_readback(call_id, render_readback)

    reset = await registration.reset(call_id)
    assert reset.cleared

    after = await registration.save_fields(call_id, {})
    assert len(after.next_missing) == 9
    stale = await registration.submit(call_id, readback.readback_version)  # type: ignore[arg-type]
    assert stale.status is SubmitStatus.STALE_READBACK


async def test_nothing_can_be_changed_or_reset_after_saving(registration: RegistrationService) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, full_draft())
    await confirmed_submit(registration, call_id)

    late = await registration.save_fields(call_id, {"city": "Waco"})
    assert late.saved == [] and late.errors[0].code == "already_submitted"
    assert not (await registration.reset(call_id)).cleared


async def test_call_outcome_statuses(registration: RegistrationService, calls: CallLogService) -> None:
    saved_call, dropped_call, failed_call = new_call_id(), new_call_id(), new_call_id()
    await registration.save_fields(saved_call, full_draft())
    await confirmed_submit(registration, saved_call)
    await registration.save_fields(dropped_call, {"first_name": "Jane"})  # hangs up before confirming
    await registration.save_fields(failed_call, {"first_name": "Jane"})
    await registration._record_failure(failed_call, "boom")

    assert (await calls.end(saved_call, ended_reason="assistant-ended-call")).status is CallStatus.COMPLETED
    abandoned = await calls.end(
        dropped_call, ended_reason="customer-ended-call", transcript="Hi", summary="Dropped"
    )
    assert abandoned.status is CallStatus.ABANDONED
    assert (abandoned.transcript, abandoned.summary, abandoned.ended_at is not None) == (
        "Hi",
        "Dropped",
        True,
    )
    assert (await calls.end(failed_call)).status is CallStatus.FAILED


async def test_a_call_with_no_prior_events_can_still_be_ended(calls: CallLogService) -> None:
    ended = await calls.end(new_call_id(), ended_reason="customer-did-not-answer")
    assert ended.status is CallStatus.ABANDONED


async def test_calls_are_listed_for_the_patient(
    registration: RegistrationService, calls: CallLogService
) -> None:
    call_id = new_call_id()
    await registration.save_fields(call_id, full_draft())
    result = await confirmed_submit(registration, call_id)
    assert result.patient is not None
    await calls.end(call_id, ended_reason="assistant-ended-call", transcript="AI: Hi\nUser: Hello")

    listed = await calls.calls_for_patient(result.patient.patient_id)
    assert [(c.call_id, c.status, c.transcript) for c in listed] == [
        (call_id, CallStatus.COMPLETED, "AI: Hi\nUser: Hello")
    ]
