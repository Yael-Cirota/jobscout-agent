"""City aliases and Israel detection."""
import re

CITY_ALIASES = {
    "Tel Aviv": ["tel aviv", "tel-aviv", "tlv", "תל אביב", "תל-אביב"],
    "Haifa": ["haifa", "חיפה"],
    "Jerusalem": ["jerusalem", "ירושלים"],
    "Herzliya": ["herzliya", "herzelia", "הרצליה"],
    "Petah Tikva": ["petah tikva", "petach tikva", "petah tikvah", "פתח תקווה"],
    "Ra'anana": ["ra'anana", "raanana", "רעננה"],
    "Be'er Sheva": ["beer sheva", "be'er sheva", "beersheba", "באר שבע"],
    "Netanya": ["netanya", "נתניה"],
    "Rehovot": ["rehovot", "רחובות"],
    "Yokneam": ["yokneam", "יקנעם"],
    "Ramat Gan": ["ramat gan", "ramat-gan", "רמת גן"],
    "Hod Hasharon": ["hod hasharon", "hod ha'sharon", "הוד השרון"],
    "Kfar Saba": ["kfar saba", "kfar sava", "כפר סבא"],
}

_REMOTE = re.compile(r"\b(remote|hybrid)\b", re.I)
_IL = re.compile(r"\b(israel|il)\b|ישראל", re.I)


def canonical_city(text):
    """Map a free-form city/location string to a canonical city, or None."""
    low = (text or "").lower()
    for city, aliases in CITY_ALIASES.items():
        if any(a in low for a in aliases):
            return city
    return None


def is_israel(location):
    return bool(_IL.search(location or "")) or canonical_city(location) is not None


def is_remote(location):
    return bool(_REMOTE.search(location or ""))


def city_of(location):
    """Canonical city if known, otherwise the first comma-separated part."""
    city = canonical_city(location)
    if city:
        return city
    first = (location or "").split(",")[0].strip()
    return first or "Israel"
