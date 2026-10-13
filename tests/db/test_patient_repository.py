"""Patient routines (fn_/sp_) through the repository, against a real Postgres 18."""

from uuid import uuid4

import pytest

from app.core.errors import DataIntegrityError
from app.db.unit_of_work import UnitOfWork
from app.domain.schemas import PatientCreate, PatientFilters
from tests.conftest import patient_payload, unique_phone


async def test_create_then_get_round_trips(uow: UnitOfWork) -> None:
    payload = PatientCreate.model_validate(patient_payload(email="T@Example.com", address_line_2="Apt 2"))
    async with uow() as repos:
        created = await repos.patients.create(payload)
    async with uow(transactional=False) as repos:
        fetched = await repos.patients.get_by_id(created.patient_id)
    assert fetched == created
    assert created.patient_id.version == 7  # uuidv7()
    assert created.email == "T@example.com"
    assert created.preferred_language == "English"
    assert created.created_at == created.updated_at


async def test_transaction_rolls_back_on_error(uow: UnitOfWork) -> None:
    phone = unique_phone()
    with pytest.raises(RuntimeError):
        async with uow() as repos:
            await repos.patients.create(PatientCreate.model_validate(patient_payload(phone_number=phone)))
            raise RuntimeError("boom")
    async with uow(transactional=False) as repos:
        assert await repos.patients.find_by_phone(phone) == []


async def test_search_filters_and_total(uow: UnitOfWork) -> None:
    phone = unique_phone()
    async with uow() as repos:
        for first in ("Ann", "Bea", "Cal"):
            await repos.patients.create(
                PatientCreate.model_validate(
                    patient_payload(first_name=first, last_name="Searchable", phone_number=phone)
                )
            )
    async with uow(transactional=False) as repos:
        page, total = await repos.patients.search(PatientFilters(last_name="SEARCHABLE", limit=2))
        assert total == 3
        assert [p.first_name for p in page] == ["Cal", "Bea"]  # newest first
        _, by_phone = await repos.patients.search(PatientFilters(phone_number=phone))
        assert by_phone == 3


async def test_partial_update_changes_only_sent_fields(uow: UnitOfWork) -> None:
    async with uow() as repos:
        created = await repos.patients.create(PatientCreate.model_validate(patient_payload(email="a@b.co")))
    async with uow() as repos:  # separate transaction, as with POST then PUT
        updated = await repos.patients.update(created.patient_id, {"city": "Dallas", "email": None})
    assert updated is not None
    assert (updated.city, updated.email, updated.last_name) == ("Dallas", None, created.last_name)
    assert updated.updated_at > created.updated_at


async def test_update_rejects_unknown_fields(uow: UnitOfWork) -> None:
    async with uow() as repos:
        created = await repos.patients.create(PatientCreate.model_validate(patient_payload()))
    with pytest.raises(DataIntegrityError):
        async with uow() as repos:
            await repos.patients.update(created.patient_id, {"patient_id": str(uuid4())})


async def test_soft_delete_hides_the_patient(uow: UnitOfWork) -> None:
    phone = unique_phone()
    async with uow() as repos:
        created = await repos.patients.create(
            PatientCreate.model_validate(patient_payload(phone_number=phone))
        )
        deleted = await repos.patients.soft_delete(created.patient_id)
        assert deleted is not None and deleted.deleted_at is not None
        assert await repos.patients.soft_delete(created.patient_id) is None  # already deleted
        assert await repos.patients.get_by_id(created.patient_id) is None
        assert await repos.patients.update(created.patient_id, {"city": "Waco"}) is None
        assert await repos.patients.find_by_phone(phone) == []


async def test_missing_patient_returns_none(uow: UnitOfWork) -> None:
    async with uow(transactional=False) as repos:
        assert await repos.patients.get_by_id(uuid4()) is None


async def test_duplicate_lookup_returns_names_only(uow: UnitOfWork) -> None:
    phone = unique_phone()
    async with uow() as repos:
        await repos.patients.create(
            PatientCreate.model_validate(patient_payload(first_name="Kid", phone_number=phone))
        )
        await repos.patients.create(
            PatientCreate.model_validate(patient_payload(first_name="Mom", phone_number=phone))
        )
        matches = await repos.patients.find_by_phone(phone)
    assert [m.first_name for m in matches] == ["Kid", "Mom"]


@pytest.mark.parametrize(
    ("override", "constraint"),
    [
        ({"state": "ZZ"}, "patients_state_fkey"),
        ({"zip_code": "123"}, "patients_zip_code_format"),
        ({"phone_number": "0125550100"}, "patients_phone_number_format"),
    ],
)
async def test_database_constraints_back_up_the_app(uow: UnitOfWork, override: dict, constraint: str) -> None:
    # model_construct skips app validation, simulating a bug or a path that bypasses it.
    valid = PatientCreate.model_validate(patient_payload()).model_dump()
    payload = PatientCreate.model_construct(**{**valid, **override})
    with pytest.raises(DataIntegrityError) as info:
        async with uow() as repos:
            await repos.patients.create(payload)
    assert info.value.constraint == constraint
