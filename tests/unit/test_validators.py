"""Every field rule, including the edge values the brief calls out."""

from datetime import date

import pytest

from app.domain.enums import Sex
from app.domain.validators import FieldRuleError, validate_field, validate_fields

TODAY = date(2026, 10, 14)


def ok(field: str, raw: object) -> object:
    return validate_field(field, raw, today=TODAY)


def code_of(field: str, raw: object) -> str:
    with pytest.raises(FieldRuleError) as info:
        validate_field(field, raw, today=TODAY)
    return info.value.code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Jane", "Jane"),
        ("  jane  ", "Jane"),
        ("JOSÉ", "José"),
        ("o'brien", "O'Brien"),
        ("O’Brien", "O'Brien"),  # curly apostrophe from speech-to-text
        ("de la cruz", "De La Cruz"),
        ("Mary-Ann", "Mary-Ann"),
        ("McDonald", "McDonald"),  # deliberate casing kept
        ("D'Angelo", "D'Angelo"),
    ],
)
def test_names_accepted_and_normalised(raw: str, expected: str) -> None:
    assert ok("last_name", raw) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("J4ne", "name_format"),
        ("Jane!", "name_format"),
        ("Jane  -  Doe", "name_format"),
        ("-Jane", "name_format"),
        ("a" * 51, "name_too_long"),
        ("", "required"),
        ("   ", "required"),
        (None, "required"),
        (42, "invalid_type"),
    ],
)
def test_names_rejected(raw: object, code: str) -> None:
    assert code_of("first_name", raw) == code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("03/05/1980", date(1980, 3, 5)),
        ("1980-03-05", date(1980, 3, 5)),
        ("3/5/1980", date(1980, 3, 5)),
        ("2024-02-29", date(2024, 2, 29)),  # leap year
        ("2026-10-14", TODAY),  # born today is allowed
        (date(1990, 1, 1), date(1990, 1, 1)),
    ],
)
def test_dob_accepted(raw: object, expected: date) -> None:
    assert ok("date_of_birth", raw) == expected


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("2026-10-15", "dob_future"),
        ("12/25/2030", "dob_future"),
        ("2023-02-29", "dob_invalid"),  # not a leap year
        ("02/30/2001", "dob_invalid"),
        ("13/01/2000", "dob_invalid"),
        ("March 5th 1980", "dob_invalid"),  # the LLM must convert spoken dates first
        ("1899-12-31", "dob_too_old"),
        ("1905-01-01", "dob_too_old"),  # 121 years old
    ],
)
def test_dob_rejected(raw: str, code: str) -> None:
    assert code_of("date_of_birth", raw) == code


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Male", Sex.MALE),
        ("female", Sex.FEMALE),
        ("M", Sex.MALE),
        ("woman", Sex.FEMALE),
        ("non-binary", Sex.OTHER),
        ("Prefer not to say", Sex.DECLINE),
        ("Decline to Answer", Sex.DECLINE),
    ],
)
def test_sex_synonyms(raw: str, expected: Sex) -> None:
    assert ok("sex", raw) is expected


def test_sex_unknown() -> None:
    assert code_of("sex", "banana") == "sex_invalid"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5125550198", "5125550198"),
        ("(512) 555-0198", "5125550198"),
        ("+1 512 555 0198", "5125550198"),
        ("1-512-555-0198", "5125550198"),
        ("512.555.0198", "5125550198"),
    ],
)
def test_phone_normalised(raw: str, expected: str) -> None:
    assert ok("phone_number", raw) == expected
    assert ok("emergency_contact_phone", raw) == expected


def test_three_digit_phone_reports_digit_count() -> None:
    with pytest.raises(FieldRuleError) as info:
        validate_field("phone_number", "555", today=TODAY)
    assert info.value.code == "phone_length"
    assert info.value.params == {"digit_count": 3}


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("512555019", "phone_length"),  # nine digits
        ("51255501981", "phone_length"),  # eleven digits not starting with 1
        ("0125550198", "phone_invalid"),  # area code starts with 0
        ("5121550198", "phone_invalid"),  # exchange starts with 1
    ],
)
def test_phone_rejected(raw: str, code: str) -> None:
    assert code_of("phone_number", raw) == code


def test_email() -> None:
    assert ok("email", "Jane.Doe@Example.COM") == "Jane.Doe@example.com"
    assert ok("email", "jane doe @ example.com") == "janedoe@example.com"  # spaces from dictation
    assert code_of("email", "jane.example.com") == "email_invalid"
    assert code_of("email", "jane@") == "email_invalid"
    assert ok("email", "") is None  # optional: empty clears it


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("TX", "TX"),
        ("tx", "TX"),
        ("Texas", "TX"),
        ("new york", "NY"),
        ("North Carolina", "NC"),
        ("the state of Texas", "TX"),
        ("Washington DC", "DC"),
        ("D.C.", "DC"),
        ("Puerto Rico", "PR"),
        ("Tennessee", "TN"),
    ],
)
def test_state_resolution(raw: str, expected: str) -> None:
    assert ok("state", raw) == expected


def test_state_unknown() -> None:
    assert code_of("state", "Atlantis") == "state_invalid"
    assert code_of("state", "ZZ") == "state_invalid"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("78704", "78704"), ("78704-1234", "78704-1234"), ("787041234", "78704-1234"), (" 78 704 ", "78704")],
)
def test_zip_accepted(raw: str, expected: str) -> None:
    assert ok("zip_code", raw) == expected


@pytest.mark.parametrize("raw", ["7870", "787045", "78704-12", "ABCDE"])
def test_zip_rejected(raw: str) -> None:
    assert code_of("zip_code", raw) == "zip_invalid"


def test_member_id() -> None:
    assert ok("insurance_member_id", "xjh-123 456") == "XJH123456"
    assert code_of("insurance_member_id", "XJH#123") == "member_id_invalid"


def test_language() -> None:
    assert ok("preferred_language", "español") == "Spanish"
    assert ok("preferred_language", "mandarin") == "Mandarin"


def test_address_and_city() -> None:
    assert ok("address_line_1", "  1200   Barton Springs Rd ") == "1200 Barton Springs Rd"
    assert code_of("address_line_1", "") == "required"
    assert ok("address_line_2", "") is None
    assert code_of("city", "12345") == "city_invalid"
    assert ok("city", "fort worth") == "Fort Worth"
    assert ok("city", "McAllen") == "McAllen"
    assert code_of("address_line_1", "x" * 101) == "address_too_long"


def test_control_characters_are_stripped() -> None:
    assert ok("city", "Aus\x00tin​") == "Austin"


def test_validate_fields_keeps_good_fields_when_one_is_bad() -> None:
    outcome = validate_fields(
        {
            "first_name": "jane",
            "date_of_birth": "2030-01-01",
            "zip_code": "78704",
            "favourite_colour": "blue",
        },
        today=TODAY,
    )
    assert outcome.values == {"first_name": "Jane", "zip_code": "78704"}
    assert {(e.field, e.code) for e in outcome.errors} == {
        ("date_of_birth", "dob_future"),
        ("favourite_colour", "unknown_field"),
    }
