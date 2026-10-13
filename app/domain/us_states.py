"""US state codes and names (same set as sql/seed/010_us_states.sql) and spoken-name resolution."""

import re

STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}  # fmt: skip


def _key(text: str) -> str:
    """Lower-case letters only: "U.S. Virgin Islands" -> "usvirginislands"."""
    return re.sub(r"[^a-z]", "", text.lower())


_BY_NAME: dict[str, str] = {_key(name): code for code, name in STATES.items()}
_ALIASES: dict[str, str] = {
    "washingtondc": "DC", "dc": "DC", "districtofcolumbia": "DC",
    "virginislands": "VI", "usvi": "VI",
    "northernmarianas": "MP", "cnmi": "MP",
    "mass": "MA", "calif": "CA", "penn": "PA", "wash": "WA",
}  # fmt: skip
_PREFIXES = ("the", "stateof", "commonwealthof")


def resolve_state(text: str) -> str | None:
    """Map a 2-letter code or a state name, in any case or punctuation, to its code."""
    stripped = text.strip()
    if len(stripped) == 2 and stripped.upper() in STATES:
        return stripped.upper()
    key = _key(stripped)
    if key not in _BY_NAME:  # "the state of Texas" -> "texas"; never strips a real name
        for prefix in _PREFIXES:
            if key.startswith(prefix) and len(key) > len(prefix):
                key = key.removeprefix(prefix)
    if len(key) == 2 and key.upper() in STATES:  # "T.X."
        return key.upper()
    return _BY_NAME.get(key) or _ALIASES.get(key)


def state_name(code: str) -> str:
    return STATES.get(code, code)
