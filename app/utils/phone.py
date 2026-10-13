"""North American Numbering Plan helpers. Phone numbers are stored as 10 bare digits."""

import re

_NANP10 = re.compile(r"^[2-9]\d{2}[2-9]\d{6}$")


def digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def to_10_digits(value: str) -> str:
    """Strip formatting and a leading country code: "+1 (512) 555-0198" -> "5125550198".

    The result is not guaranteed to be valid; check it with `is_valid_nanp`.
    """
    digits = digits_only(value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def is_valid_nanp(digits: str) -> bool:
    """Area code and exchange cannot start with 0 or 1."""
    return bool(_NANP10.match(digits))


def format_display(digits: str) -> str:
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if len(digits) == 10 else digits
