from __future__ import annotations

from catalogs.services.fulfillment_address import STRICT_PATTERN


def build_query_variants(query: str) -> list[str]:
    """Generate RÚIAN search variants from user input (strict format or free text)."""
    text = (query or "").strip()
    if len(text) < 2:
        return []

    variants: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        candidate = " ".join(value.split())
        if len(candidate) < 2 or candidate in seen:
            return
        seen.add(candidate)
        variants.append(candidate)

    add(text)
    add(text.replace(",", ""))
    add(" ".join(text.replace(",", " ").split()))

    match = STRICT_PATTERN.match(text)
    if match:
        street = match.group("street").strip()
        number = match.group("number").strip()
        city = match.group("city").strip()
        add(f"{street} {number}")
        add(f"{street} {number}, {city}")
        add(f"{street} {number} {city}")

    return variants
