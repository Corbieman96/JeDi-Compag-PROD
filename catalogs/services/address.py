import re


def normalize_czech_address(value: str) -> str:
    """Normalize user address to Czech-like readable format."""
    text = (value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace(" ,", ",").replace(",,", ",")
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1/\2", text)
    text = text.strip(" ,")

    # "456 Lipník 29443" -> "Lipník 456"
    m = re.match(r"^(?P<num>\d+[a-zA-Z]?)\s+(?P<city>[A-Za-zÁ-ž0-9 .-]+?)(?:\s+\d{5})?$", text)
    if m:
        city = re.sub(r"\s+", " ", m.group("city")).strip(" ,")
        return f"{city} {m.group('num')}".strip()

    # "Lipník 456 29443" -> "Lipník 456"
    m = re.match(r"^(?P<city>[A-Za-zÁ-ž0-9 .-]+?)\s+(?P<num>\d+[a-zA-Z]?)(?:\s+\d{5})?$", text)
    if m:
        city = re.sub(r"\s+", " ", m.group("city")).strip(" ,")
        return f"{city} {m.group('num')}".strip()

    return text


def normalize_czech_postal_code(value: str) -> str:
    """Normalize postal code to canonical Czech 5-digit form without spaces."""
    raw = (value or "").strip()
    compact = re.sub(r"\s+", " ", raw)
    match_two_three = re.fullmatch(r"(\d{2})\s*(\d{3})", compact)
    if match_two_three:
        # Historical bad format "01 293" -> canonical "29301".
        return f"{match_two_three.group(2)}{match_two_three.group(1)}"

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 5:
        if digits.startswith("0"):
            # Historical bad format was sometimes persisted as "01293" instead of "29301".
            return f"{digits[2:]}{digits[:2]}"
        return digits
    return raw
