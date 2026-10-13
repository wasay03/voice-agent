"""Turn stored values into text that sounds right when read aloud by a TTS voice."""

import calendar
import re
from datetime import date

from app.domain.us_states import state_name

_DIGIT_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_NUMBER_WORDS = (
    *_DIGIT_WORDS, "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty",
)  # fmt: skip
_SYMBOL_WORDS = {"-": "dash", "'": "apostrophe", "_": "underscore", ".": "dot", "+": "plus"}


def number_word(n: int) -> str:
    return _NUMBER_WORDS[n] if 0 <= n < len(_NUMBER_WORDS) else str(n)


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def speak_date(value: date) -> str:
    """1980-03-05 -> "March 5th, 1980"."""
    return f"{calendar.month_name[value.month]} {ordinal(value.day)}, {value.year}"


def speak_digits(digits: str) -> str:
    """ "5125550198" -> "five one two five five five zero one nine eight"."""
    return " ".join(_DIGIT_WORDS[int(ch)] for ch in digits if ch.isdigit())


def speak_phone(digits: str) -> str:
    """Grouped like a phone number is said: "five one two, five five five, zero one nine eight"."""
    if len(digits) != 10:
        return speak_digits(digits)
    return ", ".join(speak_digits(part) for part in (digits[:3], digits[3:6], digits[6:]))


def spell(text: str) -> str:
    """ "Doe" -> "D-O-E"; words are separated by commas, symbols are named ("O'Brien")."""
    words = []
    for word in text.split():
        pieces = []
        for ch in word:
            if ch.isalpha():
                pieces.append(ch.upper())
            elif ch.isdigit():
                pieces.append(_DIGIT_WORDS[int(ch)])
            else:
                pieces.append(_SYMBOL_WORDS.get(ch, ch))
        words.append("-".join(pieces))
    return ", ".join(words)


def speak_email(email: str) -> str:
    """ "jane.doe@example.com" -> "J-A-N-E dot D-O-E at example dot com"."""
    local, _, domain = email.partition("@")
    spoken_local = " dot ".join(spell(part) for part in local.split("."))
    spoken_domain = " dot ".join(domain.split("."))
    return f"{spoken_local} at {spoken_domain}"


def speak_zip(zip_code: str) -> str:
    base, _, plus4 = zip_code.partition("-")
    return f"{speak_digits(base)}, dash, {speak_digits(plus4)}" if plus4 else speak_digits(base)


def speak_member_id(member_id: str) -> str:
    """Letters as letters, digits as words, in groups of three so the caller can follow along."""
    tokens = [ch.upper() if ch.isalpha() else _DIGIT_WORDS[int(ch)] for ch in member_id if ch.isalnum()]
    return ", ".join(" ".join(tokens[i : i + 3]) for i in range(0, len(tokens), 3))


def speak_state(code: str) -> str:
    return state_name(code)


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
