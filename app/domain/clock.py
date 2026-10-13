"""The clinic's notion of "today", used for date-of-birth checks.

Configured once at startup from CLINIC_TZ; validators read it so a DOB entered late in the
evening on the US East Coast is not judged against UTC's tomorrow.
"""

from datetime import date

from app.utils.dates import today_in

_clinic_tz = "America/New_York"


def configure(tz: str) -> None:
    global _clinic_tz
    _clinic_tz = tz


def clinic_today() -> date:
    return today_in(_clinic_tz)
