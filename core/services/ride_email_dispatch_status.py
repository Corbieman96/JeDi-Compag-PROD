from __future__ import annotations

from datetime import date

from waste_docs.services.ride_document_email.dispatch_record import group_dispatch_map_for_date


def _dispatch_user_label(user) -> str:
    if not user:
        return ""
    full_name = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    return full_name or (getattr(user, "username", "") or "").strip()


def attach_email_dispatch_to_ride_groups(ride_groups: list[dict], selected_date: date) -> None:
    dispatch_map = group_dispatch_map_for_date(selected_date)
    for group in ride_groups:
        rz_id = group.get("vehicle_rz_id")
        if not rz_id:
            group["email_dispatch"] = None
            continue
        dispatch = dispatch_map.get(rz_id)
        if dispatch:
            group["email_dispatch"] = {
                "recipient_email": dispatch.recipient_email,
                "subject": dispatch.subject,
                "dispatched_at": dispatch.dispatched_at,
                "dispatched_by": _dispatch_user_label(dispatch.dispatched_by),
                "ride_count": dispatch.ride_count,
                "attachment_count": dispatch.attachment_count,
            }
        else:
            group["email_dispatch"] = None
