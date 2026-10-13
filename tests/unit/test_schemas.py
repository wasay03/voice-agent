from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.enums import Sex
from app.domain.schemas import PatientCreate, PatientFilters, PatientOut, PatientUpdate

VALID = {
    "first_name": "jane",
    "last_name": "DOE",
    "date_of_birth": "03/05/1980",
    "sex": "female",
    "phone_number": "(512) 555-0198",
    "address_line_1": "1200 Barton Springs Rd",
    "city": "Austin",
    "state": "texas",
    "zip_code": "78704",
}


def error_codes(exc: ValidationError) -> dict[str, str]:
    return {".".join(map(str, e["loc"])) or "__root__": e["type"] for e in exc.errors()}


def test_create_normalises_every_field() -> None:
    patient = PatientCreate.model_validate(VALID)
    assert patient.first_name == "Jane"
    assert patient.last_name == "Doe"
    assert patient.date_of_birth == date(1980, 3, 5)
    assert patient.sex is Sex.FEMALE
    assert patient.phone_number == "5125550198"
    assert patient.state == "TX"
    assert patient.preferred_language == "English"


def test_create_reports_rule_codes_per_field() -> None:
    with pytest.raises(ValidationError) as info:
        PatientCreate.model_validate({**VALID, "zip_code": "123", "date_of_birth": "2999-01-01"})
    assert error_codes(info.value) == {"zip_code": "zip_invalid", "date_of_birth": "dob_future"}


def test_create_rejects_unknown_fields_and_missing_required() -> None:
    body = {k: v for k, v in VALID.items() if k != "city"} | {"patient_id": "x"}
    with pytest.raises(ValidationError) as info:
        PatientCreate.model_validate(body)
    assert error_codes(info.value) == {"city": "missing", "patient_id": "extra_forbidden"}


def test_create_language_defaults_when_blank() -> None:
    assert PatientCreate.model_validate({**VALID, "preferred_language": ""}).preferred_language == "English"


def test_update_returns_only_sent_fields() -> None:
    update = PatientUpdate.model_validate({"city": "dallas", "date_of_birth": "1981-04-06", "email": None})
    assert update.changes() == {"city": "Dallas", "date_of_birth": "1981-04-06", "email": None}


def test_update_cannot_clear_required_fields_or_be_empty() -> None:
    with pytest.raises(ValidationError) as info:
        PatientUpdate.model_validate({"last_name": None})
    assert error_codes(info.value) == {"last_name": "required"}
    with pytest.raises(ValidationError) as info:
        PatientUpdate.model_validate({})
    assert error_codes(info.value) == {"__root__": "empty_update"}


def test_out_serialises_dob_as_us_date() -> None:
    row = {
        **PatientCreate.model_validate(VALID).model_dump(mode="json"),
        "patient_id": "01920000-0000-7000-8000-000000000001",
        "created_at": "2026-10-14T10:00:00+00:00",
        "updated_at": "2026-10-14T10:00:00+00:00",
    }
    assert PatientOut.model_validate(row).model_dump(mode="json")["date_of_birth"] == "03/05/1980"


def test_filters_accept_any_formatting() -> None:
    filters = PatientFilters.model_validate(
        {"date_of_birth": "1980-03-05", "phone_number": "+1 (512) 555-0198"}
    )
    assert filters.date_of_birth == date(1980, 3, 5)
    assert filters.phone_number == "5125550198"
    with pytest.raises(ValidationError):
        PatientFilters.model_validate({"limit": 500})
