"""Načtení a kontrola jízd navázaných na požadavek."""

from __future__ import annotations

from customer_requests.models import CustomerRequest
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_generated_files import has_generated_excel_file, should_generate_excel


def load_ride(ride_id: int | None) -> Pruvodka | None:
    if not ride_id:
        return None
    return Pruvodka.objects.filter(pk=ride_id).select_related("activity").first()


def ride_is_active(ride: Pruvodka | None) -> bool:
    return ride is not None and not ride.is_archived


def ride_date_matches_request(cr: CustomerRequest, ride: Pruvodka) -> bool:
    return ride.drive_date == cr.target_date


def ride_is_fulfilled(ride: Pruvodka | None) -> bool:
    if not ride_is_active(ride):
        return False
    if should_generate_excel(ride):
        return ride.status == Pruvodka.Status.GENERATED or has_generated_excel_file(ride)
    return True


def follow_up_required(cr: CustomerRequest) -> bool:
    if cr.follow_up_child_requests.exists():
        return False
    return bool(cr.has_follow_up and cr.follow_up_activity_id and cr.follow_up_target_date)


def rides_fulfill_request(cr: CustomerRequest, primary: Pruvodka | None, follow: Pruvodka | None) -> bool:
    if not ride_is_active(primary):
        return False
    if not ride_is_fulfilled(primary):
        return False
    if not follow_up_required(cr):
        return True
    if not ride_is_active(follow):
        return False
    return ride_is_fulfilled(follow)
