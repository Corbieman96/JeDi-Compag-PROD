from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import AddressCatalog
from customer_requests.request_templates.models import CustomerRequestTemplate

_VALID_WEEKDAYS = {str(i) for i in range(7)}


def _parse_decimal(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def normalize_recurrence_weekdays(raw) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (list, tuple, set)):
        parts = [str(x).strip() for x in raw]
    else:
        parts = [p.strip() for p in str(raw).split(",")]
    days = []
    seen = set()
    for part in parts:
        if part not in _VALID_WEEKDAYS or part in seen:
            continue
        seen.add(part)
        days.append(part)
    days.sort(key=int)
    return ",".join(days)


def create_customer_request_template_from_payload(
    *,
    user: AbstractBaseUser,
    payload: dict,
) -> CustomerRequestTemplate:
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValueError("Zadejte název šablony.")
    name_id = payload.get("name_id")
    waste_type_id = payload.get("waste_type_id")
    if not name_id or not waste_type_id:
        raise ValueError("Šablona vyžaduje subjekt a druh odpadu.")
    address_value = (payload.get("address_value") or "").strip()
    if not address_value:
        raise ValueError("Šablona vyžaduje adresu plnění.")
    address_obj, _ = AddressCatalog.objects.get_or_create(value=address_value)
    suffix_id = payload.get("suffix_id") or None
    if suffix_id in ("", 0, "0"):
        suffix_id = None
    activity_id = payload.get("activity_id") or None
    if activity_id in ("", 0, "0"):
        activity_id = None
    vehicle_kind_id = payload.get("vehicle_kind_id") or None
    if vehicle_kind_id in ("", 0, "0"):
        vehicle_kind_id = None

    is_recurring = bool(payload.get("is_recurring"))
    weekdays = normalize_recurrence_weekdays(payload.get("recurrence_weekdays"))
    if not is_recurring:
        weekdays = ""
    elif not weekdays:
        is_recurring = False

    return CustomerRequestTemplate.objects.create(
        title=title[:180],
        created_by=user,
        name_id=int(name_id),
        waste_type_id=int(waste_type_id),
        suffix_id=int(suffix_id) if suffix_id else None,
        address=address_obj,
        fulfillment_latitude=_parse_decimal(payload.get("fulfillment_latitude")),
        fulfillment_longitude=_parse_decimal(payload.get("fulfillment_longitude")),
        activity_id=int(activity_id) if activity_id else None,
        vehicle_kind_id=int(vehicle_kind_id) if vehicle_kind_id else None,
        facility_address_snapshot=(payload.get("facility_address_value") or "").strip()[:255],
        contact_phone=(payload.get("contact_phone") or "").strip()[:20],
        contact_note=(payload.get("contact_note") or "").strip()[:200],
        contract_number=(payload.get("contract_number") or "").strip()[:120],
        note=(payload.get("note") or "").strip()[:200],
        is_recurring=is_recurring,
        recurrence_weekdays=weekdays,
    )
