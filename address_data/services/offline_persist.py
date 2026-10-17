from __future__ import annotations

from catalogs.services.address import normalize_czech_address, normalize_czech_postal_code
from catalogs.services.fulfillment_address import normalize_fulfillment_address

from address_data.models import OfflineAddress


def display_label(city: str, street: str, house_number: str) -> str:
    city = normalize_czech_address(city or "")
    street = normalize_czech_address(street or "")
    house_number = normalize_czech_address(house_number or "")
    if street and house_number and city:
        return normalize_fulfillment_address(f"{street}, {house_number}, {city}")
    if city and house_number:
        return normalize_fulfillment_address(f"{city}, {house_number}, {city}")
    if street and house_number:
        return normalize_czech_address(f"{street} {house_number}")
    return normalize_czech_address(", ".join(part for part in [street, city] if part))


def normalize_row(row: dict) -> dict | None:
    city = normalize_czech_address((row.get("city") or "").strip())
    street = normalize_czech_address((row.get("street") or "").strip())
    house_number = normalize_czech_address((row.get("house_number") or "").strip())
    if not street and city and house_number:
        street = city
    if not city or not street or not house_number:
        return None
    postal_code = normalize_czech_postal_code((row.get("postal_code") or "").strip())
    label = normalize_czech_address((row.get("label") or "").strip())
    if not label:
        label = display_label(city, street, house_number)
    else:
        label = normalize_fulfillment_address(label) or display_label(city, street, house_number)
    return {
        "city": city,
        "street": street,
        "house_number": house_number,
        "postal_code": postal_code,
        "label": label,
        "lat": row["lat"],
        "lng": row["lng"],
    }


def upsert_offline_rows(rows: list[dict]) -> int:
    saved = 0
    for row in rows:
        normalized = normalize_row(row)
        if not normalized:
            continue
        OfflineAddress.objects.update_or_create(
            city=normalized["city"],
            street=normalized["street"],
            house_number=normalized["house_number"],
            defaults={
                "postal_code": normalized["postal_code"],
                "label": normalized["label"],
                "lat": normalized["lat"],
                "lng": normalized["lng"],
                "city_norm": normalized["city"].lower(),
                "street_norm": normalized["street"].lower(),
                "label_norm": normalized["label"].lower(),
            },
        )
        saved += 1
    return saved


def bulk_save_rows(
    rows: list[dict],
    *,
    known_keys: set[tuple[str, str, str]] | None = None,
    batch_size: int = 2000,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    pending: list[OfflineAddress] = []
    key_cache = known_keys if known_keys is not None else set()
    for row in rows:
        normalized = normalize_row(row)
        if not normalized:
            skipped += 1
            continue
        row_key = (normalized["city"], normalized["street"], normalized["house_number"])
        if row_key in key_cache:
            continue
        pending.append(
            OfflineAddress(
                city=normalized["city"],
                street=normalized["street"],
                house_number=normalized["house_number"],
                postal_code=normalized["postal_code"],
                label=normalized["label"],
                lat=normalized["lat"],
                lng=normalized["lng"],
                city_norm=normalized["city"].lower(),
                street_norm=normalized["street"].lower(),
                label_norm=normalized["label"].lower(),
            )
        )
        key_cache.add(row_key)
        if len(pending) >= batch_size:
            OfflineAddress.objects.bulk_create(pending, batch_size=batch_size)
            created += len(pending)
            pending.clear()
    if pending:
        OfflineAddress.objects.bulk_create(pending, batch_size=batch_size)
        created += len(pending)
    return created, skipped
