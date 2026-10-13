"""Date parsing and clinic-local "today"."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

_FORMATS = ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y")


def parse_date(value: str | date) -> date:
    """Accept MM/DD/YYYY (the API's format), YYYY-MM-DD (what the LLM sends) or MM-DD-YYYY.

    Raises ValueError for anything else, including impossible dates such as 02/30/2001.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = value.strip()
    for fmt in _FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {value!r}")


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


def age_on(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))


def format_us(value: date) -> str:
    return value.strftime("%m/%d/%Y")
