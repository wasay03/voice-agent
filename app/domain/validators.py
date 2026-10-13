"""One validator per patient field, shared by the REST API (via schemas.py) and the voice tools.

Each validator takes the raw value and returns the normalised value to store, or raises
`FieldRuleError` with a stable machine `code`. The API reports `code` and `message`; the voice
layer maps `code` (plus `params`) to a spoken re-prompt in app/agent/speech/phrases/.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from email_validator import EmailNotValidError, validate_email

from app.domain.enums import Sex
from app.domain.fields import REQUIRED_FIELDS, PatientField
from app.domain.us_states import resolve_state
from app.utils.dates import age_on, parse_date
from app.utils.phone import is_valid_nanp, to_10_digits
from app.utils.text import clean, has_letter, smart_title

MAX_AGE_YEARS = 120
EARLIEST_DOB = date(1900, 1, 1)

# Unicode letters (no digits or underscore), single spaces, hyphens or apostrophes between parts.
_NAME = re.compile(r"^[^\W\d_]+(?:[ '\-][^\W\d_]+)*$")
_ZIP = re.compile(r"^\d{5}(?:-\d{4})?$")
_MEMBER_ID = re.compile(r"^[A-Za-z0-9]+$")

_SEX_SYNONYMS: dict[str, Sex] = {
    **dict.fromkeys(("male", "m", "man", "boy"), Sex.MALE),
    **dict.fromkeys(("female", "f", "woman", "girl"), Sex.FEMALE),
    **dict.fromkeys(("other", "nonbinary", "non-binary", "non binary", "intersex"), Sex.OTHER),
    **dict.fromkeys(
        (
            "decline to answer",
            "decline",
            "declined",
            "prefer not to say",
            "prefer not to answer",
            "rather not say",
            "i'd rather not say",
            "no answer",
            "not specified",
        ),
        Sex.DECLINE,
    ),
}

_LANGUAGES: dict[str, str] = {
    "english": "English",
    "spanish": "Spanish",
    "español": "Spanish",
    "espanol": "Spanish",
    "castellano": "Spanish",
}


@dataclass(frozen=True)
class FieldError:
    field: str
    code: str
    message: str
    params: dict[str, Any] = field(default_factory=dict)

    def as_detail(self) -> dict[str, Any]:
        return {"field": self.field, "code": self.code, "message": self.message}


class FieldRuleError(ValueError):
    def __init__(self, code: str, message: str, **params: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.params = params


# ---------------------------------------------------------------------------------------------
# Per-field validators. Each receives a non-empty value; emptiness is handled by validate_field.
# ---------------------------------------------------------------------------------------------


def _text(raw: Any) -> str:
    if not isinstance(raw, str):
        raise FieldRuleError("invalid_type", "Must be a string.")
    return clean(raw)


def _person_name(raw: Any, *, max_len: int = 50) -> str:
    value = _text(raw)
    if len(value) > max_len:
        raise FieldRuleError("name_too_long", f"Must be at most {max_len} characters.", max_length=max_len)
    if not _NAME.match(value):
        raise FieldRuleError("name_format", "Use letters only, with single spaces, hyphens or apostrophes.")
    return smart_title(value)


def _date_of_birth(raw: Any, *, today: date) -> date:
    try:
        value = parse_date(raw) if isinstance(raw, str | date) else None
    except ValueError:
        value = None
    if value is None:
        raise FieldRuleError("dob_invalid", "Must be a real date in MM/DD/YYYY or YYYY-MM-DD format.")
    if value > today:
        raise FieldRuleError("dob_future", "Date of birth cannot be in the future.")
    if value < EARLIEST_DOB or age_on(value, today) > MAX_AGE_YEARS:
        raise FieldRuleError("dob_too_old", f"Date of birth implies an age over {MAX_AGE_YEARS}.")
    return value


def _sex(raw: Any) -> Sex:
    value = _text(raw).lower()
    if value in _SEX_SYNONYMS:
        return _SEX_SYNONYMS[value]
    raise FieldRuleError("sex_invalid", "Must be one of: Male, Female, Other, Decline to Answer.")


def _phone(raw: Any) -> str:
    digits = to_10_digits(raw if isinstance(raw, str) else str(raw))
    if len(digits) != 10:
        raise FieldRuleError(
            "phone_length", f"A US phone number has 10 digits; got {len(digits)}.", digit_count=len(digits)
        )
    if not is_valid_nanp(digits):
        raise FieldRuleError("phone_invalid", "Area code and exchange cannot start with 0 or 1.")
    return digits


def _email(raw: Any) -> str:
    value = _text(raw).replace(" ", "")
    if len(value) > 254:
        raise FieldRuleError("email_invalid", "Email address is too long.")
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise FieldRuleError("email_invalid", f"Not a valid email address: {exc}.") from None


def _bounded_text(raw: Any, *, max_len: int, code: str) -> str:
    value = _text(raw)
    if len(value) > max_len:
        raise FieldRuleError(code, f"Must be at most {max_len} characters.", max_length=max_len)
    return value


def _city(raw: Any) -> str:
    value = _bounded_text(raw, max_len=100, code="city_too_long")
    if not has_letter(value):
        raise FieldRuleError("city_invalid", "City must contain letters.")
    return smart_title(value)


def _state(raw: Any) -> str:
    code = resolve_state(_text(raw))
    if code is None:
        raise FieldRuleError("state_invalid", "Must be a US state name or 2-letter abbreviation.")
    return code


def _zip(raw: Any) -> str:
    value = re.sub(r"\s", "", _text(raw))
    if re.fullmatch(r"\d{9}", value):
        value = f"{value[:5]}-{value[5:]}"
    if not _ZIP.match(value):
        raise FieldRuleError("zip_invalid", "ZIP code must be 5 digits or ZIP+4 (12345-6789).")
    return value


def _member_id(raw: Any) -> str:
    value = re.sub(r"[\s\-]", "", _text(raw)).upper()
    if not _MEMBER_ID.match(value) or len(value) > 30:
        raise FieldRuleError("member_id_invalid", "Member ID must be letters and digits, at most 30.")
    return value


def _language(raw: Any) -> str:
    value = _bounded_text(raw, max_len=40, code="language_too_long")
    if not has_letter(value):
        raise FieldRuleError("language_invalid", "Language must contain letters.")
    return _LANGUAGES.get(value.lower(), smart_title(value))


def _contact_name(raw: Any) -> str:
    value = _bounded_text(raw, max_len=100, code="name_too_long")
    if not has_letter(value) or any(ch.isdigit() for ch in value):
        raise FieldRuleError("name_format", "Use letters only.")
    return smart_title(value)


_VALIDATORS: dict[PatientField, Callable[..., Any]] = {
    PatientField.FIRST_NAME: _person_name,
    PatientField.LAST_NAME: _person_name,
    PatientField.DATE_OF_BIRTH: _date_of_birth,
    PatientField.SEX: _sex,
    PatientField.PHONE_NUMBER: _phone,
    PatientField.EMAIL: _email,
    PatientField.ADDRESS_LINE_1: lambda raw: _bounded_text(raw, max_len=100, code="address_too_long"),
    PatientField.ADDRESS_LINE_2: lambda raw: _bounded_text(raw, max_len=100, code="address_too_long"),
    PatientField.CITY: _city,
    PatientField.STATE: _state,
    PatientField.ZIP_CODE: _zip,
    PatientField.INSURANCE_PROVIDER: lambda raw: _bounded_text(raw, max_len=100, code="insurance_too_long"),
    PatientField.INSURANCE_MEMBER_ID: _member_id,
    PatientField.PREFERRED_LANGUAGE: _language,
    PatientField.EMERGENCY_CONTACT_NAME: _contact_name,
    PatientField.EMERGENCY_CONTACT_PHONE: _phone,
}


def _is_empty(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and not clean(raw))


def validate_field(name: PatientField | str, raw: Any, *, today: date) -> Any:
    """Return the normalised value for one field, or raise FieldRuleError.

    An empty value is an error for required fields and means "clear it" (None) for optional ones.
    """
    field_ = PatientField(name)
    if _is_empty(raw):
        if field_ in REQUIRED_FIELDS:
            raise FieldRuleError("required", "This field is required.")
        return None
    validator = _VALIDATORS[field_]
    if field_ is PatientField.DATE_OF_BIRTH:
        return validator(raw, today=today)
    return validator(raw)


@dataclass
class ValidationOutcome:
    values: dict[str, Any] = field(default_factory=dict)
    errors: list[FieldError] = field(default_factory=list)


def validate_fields(data: Mapping[str, Any], *, today: date) -> ValidationOutcome:
    """Validate each field independently: one bad field never discards the good ones."""
    outcome = ValidationOutcome()
    for name, raw in data.items():
        try:
            field_ = PatientField(name)
        except ValueError:
            outcome.errors.append(FieldError(name, "unknown_field", "Not a patient field."))
            continue
        try:
            outcome.values[field_.value] = validate_field(field_, raw, today=today)
        except FieldRuleError as exc:
            outcome.errors.append(FieldError(field_.value, exc.code, exc.message, exc.params))
    return outcome
