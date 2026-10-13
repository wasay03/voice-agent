"""The patient fields, which are required, and the order the agent prefers to ask for them."""

from enum import StrEnum


class PatientField(StrEnum):
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    DATE_OF_BIRTH = "date_of_birth"
    SEX = "sex"
    PHONE_NUMBER = "phone_number"
    EMAIL = "email"
    ADDRESS_LINE_1 = "address_line_1"
    ADDRESS_LINE_2 = "address_line_2"
    CITY = "city"
    STATE = "state"
    ZIP_CODE = "zip_code"
    INSURANCE_PROVIDER = "insurance_provider"
    INSURANCE_MEMBER_ID = "insurance_member_id"
    PREFERRED_LANGUAGE = "preferred_language"
    EMERGENCY_CONTACT_NAME = "emergency_contact_name"
    EMERGENCY_CONTACT_PHONE = "emergency_contact_phone"


# In the order the agent asks for them; `next_missing` preserves this order.
REQUIRED_FIELDS: tuple[PatientField, ...] = (
    PatientField.FIRST_NAME,
    PatientField.LAST_NAME,
    PatientField.DATE_OF_BIRTH,
    PatientField.SEX,
    PatientField.PHONE_NUMBER,
    PatientField.ADDRESS_LINE_1,
    PatientField.CITY,
    PatientField.STATE,
    PatientField.ZIP_CODE,
)

OPTIONAL_FIELDS: tuple[PatientField, ...] = tuple(f for f in PatientField if f not in REQUIRED_FIELDS)

ALL_FIELDS: frozenset[str] = frozenset(f.value for f in PatientField)
