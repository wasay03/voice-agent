from datetime import date

import pytest

from app.agent.speech import formatters as fmt
from app.agent.speech.phrases.en import reprompt
from app.agent.speech.readback import ADDRESS_EXTRAS, IDENTITY_CONTACT, render_readback

DRAFT = {
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1980-03-05",
    "sex": "Female",
    "phone_number": "5125550198",
    "address_line_1": "1200 Barton Springs Rd",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78704",
}


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (1, "1st"),
        (2, "2nd"),
        (3, "3rd"),
        (4, "4th"),
        (11, "11th"),
        (12, "12th"),
        (13, "13th"),
        (21, "21st"),
        (22, "22nd"),
        (23, "23rd"),
        (30, "30th"),
        (31, "31st"),
    ],
)
def test_ordinals(day: int, expected: str) -> None:
    assert fmt.ordinal(day) == expected


def test_speak_date() -> None:
    assert fmt.speak_date(date(1980, 3, 5)) == "March 5th, 1980"
    assert fmt.speak_date(date(2000, 12, 31)) == "December 31st, 2000"


def test_phone_is_grouped_and_zero_is_spoken() -> None:
    assert fmt.speak_phone("5125550198") == "five one two, five five five, zero one nine eight"


def test_spelling() -> None:
    assert fmt.spell("Doe") == "D-O-E"
    assert fmt.spell("De La Cruz") == "D-E, L-A, C-R-U-Z"
    assert fmt.spell("O'Brien") == "O-apostrophe-B-R-I-E-N"
    assert fmt.spell("Mary-Ann") == "M-A-R-Y-dash-A-N-N"


def test_email_and_zip_and_member_id() -> None:
    assert fmt.speak_email("jane.doe@example.com") == "J-A-N-E dot D-O-E at example dot com"
    assert fmt.speak_zip("78704") == "seven eight seven zero four"
    assert fmt.speak_zip("78704-1234") == "seven eight seven zero four, dash, one two three four"
    assert fmt.speak_member_id("XJH123456") == "X J H, one two three, four five six"


def test_readback_has_two_chunks_with_everything_required() -> None:
    chunks = render_readback(DRAFT)
    assert [c.key for c in chunks] == [IDENTITY_CONTACT, ADDRESS_EXTRAS]
    identity, address = chunks
    assert "Jane Doe" in identity.text and "D-O-E" in identity.text
    assert "March 5th, 1980" in identity.text
    assert "five one two, five five five, zero one nine eight" in identity.text
    assert "female" in identity.text
    assert "email" not in identity.text
    assert "Austin, Texas, seven eight seven zero four" in address.text
    assert "insurance" not in address.text.lower()


def test_readback_includes_optional_fields_when_present() -> None:
    draft = {
        **DRAFT,
        "email": "jane.doe@example.com",
        "address_line_2": "Apt 4B",
        "insurance_provider": "Blue Cross",
        "insurance_member_id": "XJH123456",
        "emergency_contact_name": "John Doe",
        "emergency_contact_phone": "5125550199",
        "preferred_language": "Spanish",
        "sex": "Decline to Answer",
    }
    identity, address = render_readback(draft)
    assert "J-A-N-E dot D-O-E at example dot com" in identity.text
    assert "prefer not to say" in identity.text
    assert "1200 Barton Springs Rd, Apt 4B, Austin" in address.text
    assert "Blue Cross, member ID X J H, one two three, four five six" in address.text
    assert "John Doe, at five one two, five five five, zero one nine nine" in address.text
    assert "preferred language is Spanish" in address.text


def test_readback_text_changes_when_a_field_changes() -> None:
    before = render_readback(DRAFT)
    after = render_readback({**DRAFT, "last_name": "Davis"})
    assert before[0].text != after[0].text
    assert before[1].text == after[1].text  # a name correction leaves the address chunk alone


@pytest.mark.parametrize(
    ("field", "code", "params", "expected"),
    [
        ("date_of_birth", "dob_future", {}, "future"),
        ("phone_number", "phone_length", {"digit_count": 9}, "nine digits"),
        ("phone_number", "phone_length", {"digit_count": 3}, "three digits"),
        ("zip_code", "zip_invalid", {}, "five digits"),
        ("state", "state_invalid", {}, "Which state"),
        ("city", "required", {}, "I still need your city"),
        ("email", "email_invalid", {}, "spell it out"),
        ("last_name", "something_new", {}, "last name again"),
    ],
)
def test_reprompts_are_field_specific(field: str, code: str, params: dict, expected: str) -> None:
    assert expected in reprompt(field, code, params)
