from __future__ import annotations

from customer_requests.request_templates.models import CustomerRequestTemplate


def _coord_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def customer_request_template_to_json(row: CustomerRequestTemplate) -> dict:
    return {
        "id": row.pk,
        "title": row.title,
        "name_id": row.name_id,
        "name_value": row.name.value if row.name_id else "",
        "waste_type_id": row.waste_type_id,
        "suffix_id": row.suffix_id,
        "address_value": row.address.value if row.address_id else "",
        "fulfillment_latitude": _coord_str(row.fulfillment_latitude),
        "fulfillment_longitude": _coord_str(row.fulfillment_longitude),
        "activity_id": row.activity_id,
        "vehicle_kind_id": row.vehicle_kind_id,
        "facility_address_value": row.facility_address_snapshot or "",
        "contact_phone": row.contact_phone or "",
        "contact_note": row.contact_note or "",
        "contract_number": row.contract_number or "",
        "note": row.note or "",
        "is_recurring": bool(row.is_recurring),
        "recurrence_weekdays": row.recurrence_weekdays or "",
        "created_by_id": row.created_by_id,
        "created_by_label": row.created_by.get_username() if row.created_by_id else "",
    }
