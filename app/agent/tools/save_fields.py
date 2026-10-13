"""save_fields: record or correct any patient fields the caller just gave, in any order."""

from typing import Any

from pydantic import BaseModel, Field

from app.agent.context import ToolContext
from app.agent.speech.phrases.en import reprompt
from app.agent.tools.base import Tool
from app.domain.fields import PatientField
from app.domain.validators import FieldError
from app.services.registration_service import RegistrationService

_FIELD_HELP = {
    PatientField.FIRST_NAME: "Letters only.",
    PatientField.LAST_NAME: "Letters only. If the caller spelled it out, join the letters into the word.",
    PatientField.DATE_OF_BIRTH: "YYYY-MM-DD. Convert spoken dates yourself.",
    PatientField.SEX: "One of: Male, Female, Other, Decline to Answer.",
    PatientField.PHONE_NUMBER: (
        "10 digits. If the caller says the number they are calling from is fine, send CALLER_ID."
    ),
    PatientField.EMAIL: "Full email address.",
    PatientField.ADDRESS_LINE_1: "Street number and name.",
    PatientField.ADDRESS_LINE_2: "Apartment, suite or unit, if any.",
    PatientField.CITY: "City name.",
    PatientField.STATE: "Two-letter code or full state name.",
    PatientField.ZIP_CODE: "5 digits, or ZIP+4.",
    PatientField.INSURANCE_PROVIDER: "Insurance company name.",
    PatientField.INSURANCE_MEMBER_ID: "Letters and digits only.",
    PatientField.PREFERRED_LANGUAGE: "Language name, for example English or Spanish.",
    PatientField.EMERGENCY_CONTACT_NAME: "Full name.",
    PatientField.EMERGENCY_CONTACT_PHONE: "10 digits.",
}


class SaveFieldsArgs(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)


def render_errors(errors: list[FieldError]) -> list[dict[str, str]]:
    return [{"field": e.field, "code": e.code, "say": reprompt(e.field, e.code, e.params)} for e in errors]


class SaveFieldsTool(Tool):
    name = "save_fields"
    description = (
        "Save or correct any patient fields the caller just provided. Call it immediately, even in the "
        "middle of the readback. Send only the fields the caller just gave or changed; several at once "
        "is fine. Convert to canonical form first. To remove an optional field, send an empty string."
    )
    Args = SaveFieldsArgs

    def __init__(self, registration: RegistrationService) -> None:
        self._registration = registration

    def parameters(self) -> dict[str, Any]:
        properties = {f.value: {"type": "string", "description": _FIELD_HELP[f]} for f in PatientField}
        return {
            "type": "object",
            "properties": {
                "fields": {"type": "object", "properties": properties, "additionalProperties": False}
            },
            "required": ["fields"],
        }

    async def run(self, ctx: ToolContext, args: SaveFieldsArgs) -> dict[str, Any]:
        # A model often sends null for fields it was not given; null must not clear anything.
        given = {k: v for k, v in args.fields.items() if v is not None}
        result = await self._registration.save_fields(ctx.call_id, given, caller_number=ctx.caller_number)
        return {
            "saved": result.saved,
            "errors": render_errors(result.errors),
            "next_missing": result.next_missing,
            "existing_patients": [
                {"patient_id": str(p.patient_id), "first_name": p.first_name, "last_name": p.last_name}
                for p in result.existing_patients
            ],
            "mode": result.mode.value,
        }
