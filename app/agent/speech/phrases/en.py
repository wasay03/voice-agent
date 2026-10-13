"""What the agent says when a field is rejected, keyed by the validator's error code.

Hints are short, specific to the field, and end with a question that re-asks for exactly that
field. The agent says them in its own voice; they exist so the wording is consistent and tested.
"""

from app.agent.speech.formatters import number_word

FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "date_of_birth": "date of birth",
    "sex": "sex",
    "phone_number": "phone number",
    "email": "email address",
    "address_line_1": "street address",
    "address_line_2": "apartment or unit number",
    "city": "city",
    "state": "state",
    "zip_code": "ZIP code",
    "insurance_provider": "insurance provider",
    "insurance_member_id": "insurance member ID",
    "preferred_language": "preferred language",
    "emergency_contact_name": "emergency contact's name",
    "emergency_contact_phone": "emergency contact's phone number",
}

_HINTS = {
    "required": "I still need your {label}. What is it?",
    "name_format": "I just need letters for the name. Could you spell it for me?",
    "name_too_long": "That's longer than I can fit. Could you give me just the name?",
    "dob_future": "That date would be in the future. Could you give me your date of birth again?",
    "dob_invalid": "I didn't catch that as a date. What's your date of birth, including the year?",
    "dob_too_old": "That would make the patient over a hundred and twenty. "
    "Could you say the date of birth again?",
    "sex_invalid": "Would you say male, female, other, or that you'd prefer not to answer?",
    "phone_length": "I only got {digit_count_word} digits. "
    "Could you say the whole number again, including the area code?",
    "phone_invalid": "That doesn't sound like a valid number. Could you say it again with the area code?",
    "caller_id_unavailable": "I don't see a number on this call. What's the best number to reach you?",
    "email_invalid": "I couldn't make that into an email address. Could you spell it out for me?",
    "state_invalid": "Which state is that in?",
    "zip_invalid": "ZIP codes are five digits. What's yours?",
    "city_invalid": "What city is that in?",
    "address_too_long": "That's longer than I can fit. Could you give me just the street address?",
    "member_id_invalid": "Member IDs are letters and numbers only. Could you read it again?",
    "language_invalid": "What language would you prefer to speak?",
    "already_submitted": "That registration was already saved, so I can't change it on this call.",
}
_DEFAULT = "Sorry, I didn't catch that. Could you say your {label} again?"


def reprompt(field: str, code: str, params: dict | None = None) -> str:
    """The spoken re-ask for one rejected field."""
    params = dict(params or {})
    if "digit_count" in params:
        params["digit_count_word"] = number_word(int(params["digit_count"]))
    label = FIELD_LABELS.get(field, "answer")
    template = _HINTS.get(code, _DEFAULT)
    return template.format(label=label, **params)


def all_set(first_name: str) -> str:
    """The closing line after a successful save (the brief asks for "You're all set, [First Name].")."""
    return f"You're all set, {first_name}. Thanks for calling, and have a great day. Goodbye."


# Spoken when saving the registration fails.
SAVE_RETRY = "I'm having trouble saving that. Let me try once more."
SAVE_FAILED = (
    "I'm sorry, I wasn't able to save your information just now. "
    "Someone from the clinic will follow up with you. Thank you for calling."
)
SAVE_WORKING = "One moment while I save that."

# Spoken when a tool itself fails (bad arguments, timeout, bug): keeps the call moving.
TOOL_TROUBLE = "Sorry, I had a little trouble with that. Could you say that again?"
