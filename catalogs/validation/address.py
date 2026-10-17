import re


PATTERN_STREET = re.compile(r"^[A-Za-zÁ-ž0-9 .-]+(?:,\s*)?\d+[a-zA-Z]?(?:/\d+)?(?:\s+[A-Za-zÁ-ž0-9 .-]+)?$")
PATTERN_CITY_VILLAGE = re.compile(r"^[A-Za-zÁ-ž0-9 .-]+\s+\([^)]+\)\s+\d+[a-zA-Z]?$")


def is_valid_fulfillment_address(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    return bool(PATTERN_STREET.match(text) or PATTERN_CITY_VILLAGE.match(text))
