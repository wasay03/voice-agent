"""Text clean-up shared by every free-text field."""

import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "`": "'"})
_DASHES = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-"})


def clean(value: str) -> str:
    """NFC-normalise, drop control/format characters, unify apostrophes and dashes, collapse spaces."""
    kept = []
    for ch in unicodedata.normalize("NFC", value):
        if ch in "\t\n\r":
            kept.append(" ")
        elif unicodedata.category(ch) not in ("Cc", "Cf"):  # control and invisible format characters
            kept.append(ch)
    value = "".join(kept).translate(_APOSTROPHES).translate(_DASHES)
    return _WHITESPACE.sub(" ", value).strip()


def smart_title(value: str) -> str:
    """Title-case input that arrived all upper or all lower case; keep deliberate casing ("McDonald").

    Each part between spaces, hyphens and apostrophes is capitalised: "o'brien-smith" -> "O'Brien-Smith".
    """
    letters = [ch for ch in value if ch.isalpha()]
    if not letters or not (all(ch.isupper() for ch in letters) or all(ch.islower() for ch in letters)):
        return value
    return re.sub(r"[^\W\d_]+", lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(), value)


def has_letter(value: str) -> bool:
    return any(ch.isalpha() for ch in value)
