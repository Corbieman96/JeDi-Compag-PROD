import re

from catalogs.services.address import normalize_czech_address


# Číslo popisné/orientační: aspoň jedna číslice, volitelně s písmeny
# (např. 123, 123a, 123/45, 123/45b) i s vedoucím písmenem (např. M2, A5 – areály).
_NUMBER = r"[A-Za-z]*\d+[A-Za-z0-9]*(?:/\d+[A-Za-z0-9]*)?"

STRICT_PATTERN = re.compile(rf"^(?P<street>[^,]+),\s*(?P<number>{_NUMBER}),\s*(?P<city>[^,]+)$")
CITY_NUMBER_PATTERN = re.compile(rf"^(?P<city>[^,]+),\s*(?P<number>{_NUMBER})$")
CP_CITY_PATTERN = re.compile(
    rf"^(?:č\.?\s*p\.?\s*)?(?P<number>{_NUMBER})\s*,\s*(?:(?:\d{{3}}\s?\d{{2}})\s+)?(?P<city>.+)$",
    re.IGNORECASE,
)


def _clean_city(text: str) -> str:
    city = re.sub(r"\s+", " ", (text or "")).strip(" ,")
    city = re.sub(r"^\d{3}\s?\d{2}\s+", "", city).strip(" ,")
    return city


def normalize_fulfillment_address(value: str) -> str:
    text = normalize_czech_address((value or "").strip())
    if not text:
        return ""

    m = STRICT_PATTERN.match(text)
    if m:
        street = re.sub(r"\s+", " ", m.group("street")).strip(" ,")
        number = re.sub(r"\s+", "", m.group("number")).strip(" ,")
        city = _clean_city(m.group("city"))
        return f"{street}, {number}, {city}"

    m = CITY_NUMBER_PATTERN.match(text)
    if m:
        city = _clean_city(m.group("city"))
        number = re.sub(r"\s+", "", m.group("number")).strip(" ,")
        if city and number:
            # Village address fallback: use city in street slot to keep strict app format.
            return f"{city}, {number}, {city}"

    m = CP_CITY_PATTERN.match(text)
    if m:
        city = _clean_city(m.group("city"))
        number = re.sub(r"\s+", "", m.group("number")).strip(" ,")
        if city and number:
            return f"{city}, {number}, {city}"

    m = re.match(rf"^(?P<street>.+?)\s+(?P<number>{_NUMBER})\s+(?P<city>.+)$", text)
    if m:
        street = re.sub(r"\s+", " ", m.group("street")).strip(" ,")
        number = re.sub(r"\s+", "", m.group("number")).strip(" ,")
        city = _clean_city(m.group("city"))
        if street and number and city:
            return f"{street}, {number}, {city}"

    m = re.match(rf"^(?P<city>.+?)\s+(?P<number>{_NUMBER})$", text)
    if m:
        city = re.sub(r"\s+", " ", m.group("city")).strip(" ,")
        number = re.sub(r"\s+", "", m.group("number")).strip(" ,")
        if city and number:
            return f"{city}, {number}, {city}"

    return text


def is_valid_fulfillment_address_strict(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return bool(STRICT_PATTERN.match(text))
