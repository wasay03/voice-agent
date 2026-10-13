"""Patient models for the REST API and the service layer.

Every field goes through `validators.validate_field`, so the API and the voice tools apply exactly
the same rules. A rule failure becomes a Pydantic error whose `type` is the validator's code
(e.g. `dob_future`), which the API reports in `error.details[].code`.
"""

from datetime import date, datetime
from typing import Any, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_core import PydanticCustomError

from app.domain.clock import clinic_today
from app.domain.enums import Sex
from app.domain.validators import FieldRuleError, validate_field
from app.utils.dates import format_us, parse_date
from app.utils.phone import to_10_digits
from app.utils.text import clean

DEFAULT_LANGUAGE = "English"


def _apply_rules(value: Any, info: ValidationInfo) -> Any:
    try:
        return validate_field(info.field_name, value, today=clinic_today())  # type: ignore[arg-type]
    except FieldRuleError as exc:
        raise PydanticCustomError(exc.code, exc.message) from None


class PatientCreate(BaseModel):
    """Body of POST /patients and the payload a confirmed voice registration saves."""

    model_config = ConfigDict(extra="forbid")

    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: str | None = None
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    zip_code: str
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = DEFAULT_LANGUAGE
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _rules(cls, value: Any, info: ValidationInfo) -> Any:
        return _apply_rules(value, info)

    @model_validator(mode="after")
    def _default_language(self) -> Self:
        if self.preferred_language is None:
            self.preferred_language = DEFAULT_LANGUAGE
        return self


class PatientUpdate(BaseModel):
    """Body of PUT /patients/{id}: any subset of fields. Required fields cannot be cleared."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    email: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _rules(cls, value: Any, info: ValidationInfo) -> Any:
        return _apply_rules(value, info)

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise PydanticCustomError("empty_update", "Provide at least one field to update.")
        if "preferred_language" in self.model_fields_set and self.preferred_language is None:
            self.preferred_language = DEFAULT_LANGUAGE
        return self

    def changes(self) -> dict[str, Any]:
        """Only the fields the client sent, JSON-ready (ISO dates), for sp_patient_update's p_changes."""
        return self.model_dump(mode="json", exclude_unset=True)


class PatientOut(BaseModel):
    """A stored patient as the API returns it. Dates of birth go out as MM/DD/YYYY."""

    patient_id: UUID
    first_name: str
    last_name: str
    date_of_birth: date
    sex: Sex
    phone_number: str
    email: str | None = None
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state: str
    zip_code: str
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None

    @field_serializer("date_of_birth")
    def _us_date(self, value: date) -> str:
        return format_us(value)


class PatientFilters(BaseModel):
    """Query parameters of GET /patients. Any formatting of phone and date is accepted."""

    model_config = ConfigDict(extra="forbid")

    last_name: str | None = None
    date_of_birth: date | None = None
    phone_number: str | None = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)

    @field_validator("last_name", mode="before")
    @classmethod
    def _last_name(cls, value: Any) -> str | None:
        return (clean(value) or None) if isinstance(value, str) else value

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _date(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip():
            try:
                return parse_date(value)
            except ValueError:
                raise PydanticCustomError("dob_invalid", "Use MM/DD/YYYY or YYYY-MM-DD.") from None
        return value or None

    @field_validator("phone_number", mode="before")
    @classmethod
    def _phone(cls, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        digits = to_10_digits(value)
        if len(digits) != 10:
            raise PydanticCustomError("phone_length", "A US phone number has 10 digits.")
        return digits
