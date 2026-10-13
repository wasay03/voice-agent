"""Build the confirmation readback from the draft, as spoken chunks.

The text is generated here, not by the LLM, so what the caller hears is exactly what will be
saved. Each chunk is read verbatim; the agent asks "Is that all correct?" after each one.
"""

from datetime import date
from typing import Any

from app.agent.speech import formatters as fmt
from app.domain.entities import ReadbackChunk
from app.domain.enums import Sex

IDENTITY_CONTACT = "identity_contact"
ADDRESS_EXTRAS = "address_extras"


def _sex_sentence(sex: str) -> str:
    if sex == Sex.DECLINE.value:
        return "You'd prefer not to say your sex."
    return f"I have you down as {sex.lower()}."


def _identity_contact(draft: dict[str, Any]) -> ReadbackChunk:
    sentences = [
        f"I have your name as {draft['first_name']} {draft['last_name']}, "
        f"last name spelled {fmt.spell(draft['last_name'])}.",
        f"Your date of birth is {fmt.speak_date(date.fromisoformat(draft['date_of_birth']))}.",
        _sex_sentence(draft["sex"]),
        f"Your phone number is {fmt.speak_phone(draft['phone_number'])}.",
    ]
    used = ["first_name", "last_name", "date_of_birth", "sex", "phone_number"]
    if draft.get("email"):
        sentences.append(f"Your email is {fmt.speak_email(draft['email'])}.")
        used.append("email")
    return ReadbackChunk(key=IDENTITY_CONTACT, text=" ".join(sentences), fields=used)


def _address_extras(draft: dict[str, Any]) -> ReadbackChunk:
    street = draft["address_line_1"]
    if draft.get("address_line_2"):
        street = f"{street}, {draft['address_line_2']}"
    sentences = [
        f"Your address is {street}, {draft['city']}, {fmt.speak_state(draft['state'])}, "
        f"{fmt.speak_zip(draft['zip_code'])}."
    ]
    used = ["address_line_1", "address_line_2", "city", "state", "zip_code"]

    provider, member_id = draft.get("insurance_provider"), draft.get("insurance_member_id")
    if provider and member_id:
        sentences.append(f"Your insurance is {provider}, member ID {fmt.speak_member_id(member_id)}.")
    elif provider:
        sentences.append(f"Your insurance is {provider}.")
    elif member_id:
        sentences.append(f"Your insurance member ID is {fmt.speak_member_id(member_id)}.")
    used += ["insurance_provider", "insurance_member_id"]

    contact, contact_phone = draft.get("emergency_contact_name"), draft.get("emergency_contact_phone")
    if contact and contact_phone:
        sentences.append(f"Your emergency contact is {contact}, at {fmt.speak_phone(contact_phone)}.")
    elif contact:
        sentences.append(f"Your emergency contact is {contact}.")
    elif contact_phone:
        sentences.append(f"Your emergency contact number is {fmt.speak_phone(contact_phone)}.")
    used += ["emergency_contact_name", "emergency_contact_phone"]

    if draft.get("preferred_language"):
        sentences.append(f"Your preferred language is {draft['preferred_language']}.")
        used.append("preferred_language")
    return ReadbackChunk(key=ADDRESS_EXTRAS, text=" ".join(sentences), fields=used)


def render_readback(draft: dict[str, Any], language: str = "en") -> list[ReadbackChunk]:
    """Two chunks: identity and contact, then address and extras. Requires the required fields."""
    return [_identity_contact(draft), _address_extras(draft)]
