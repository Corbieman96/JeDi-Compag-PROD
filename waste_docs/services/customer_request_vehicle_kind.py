"""Efektivní druh vozidla u CustomerRequest a výchozí řidič/RZ pro předvyplnění."""

from __future__ import annotations

from datetime import date

from django.db.models import Q

from catalogs.models import DriverProfile, VehicleKindCatalog, VehicleRzProfile
from catalogs.services.driver_absence import driver_ids_fully_absent_on_date
from customer_requests.models import CustomerRequest


def effective_vehicle_kind(cr: CustomerRequest) -> VehicleKindCatalog | None:
    """FK na požadavku, jinak jediný druh vozidla u činnosti."""
    if cr.vehicle_kind_id:
        return cr.vehicle_kind
    activity = getattr(cr, "activity", None)
    if not activity or not activity.pk:
        return None
    prefetched = getattr(activity, "_prefetched_objects_cache", {}).get("vehicle_kinds")
    if prefetched is not None:
        kinds = sorted(prefetched, key=lambda k: (k.sort_order, k.name or "", k.pk))
        if len(kinds) == 1:
            return kinds[0]
        return None
    kinds = list(activity.vehicle_kinds.order_by("sort_order", "name", "pk")[:2])
    if len(kinds) == 1:
        return kinds[0]
    return None


def effective_vehicle_kind_id(cr: CustomerRequest) -> int | None:
    vk = effective_vehicle_kind(cr)
    return vk.pk if vk else None


def effective_vehicle_kind_label(cr: CustomerRequest) -> str:
    vk = effective_vehicle_kind(cr)
    return vk.display_label() if vk else ""


def _pick_vehicle_rz_id_for_driver(driver: DriverProfile, *, vehicle_kind_id: int) -> int | None:
    prof_qs = VehicleRzProfile.objects.filter(vehicle_kinds__id=vehicle_kind_id).select_related("rz")
    drz_ids = list(driver.allowed_vehicle_rz.values_list("pk", flat=True))
    if drz_ids:
        prof = prof_qs.filter(pk__in=drz_ids).order_by("rz__value").first()
        if prof:
            return prof.rz_id
    prof = prof_qs.order_by("rz__value").first()
    return prof.rz_id if prof else None


def pick_default_driver_and_rz_for_customer_request(
    cr: CustomerRequest,
    drive_date: date | None,
) -> tuple[int | None, int | None]:
    """První dostupný řidič pro činnost + druh vozidla a odpovídající RZ."""
    vk_id = effective_vehicle_kind_id(cr)
    if not vk_id or not cr.activity_id:
        return None, None

    drivers = (
        DriverProfile.objects.filter(
            Q(allowed_vehicle_kinds__activities__id=cr.activity_id)
            | Q(allowed_vehicle_rz__vehicle_kinds__activities__id=cr.activity_id)
        )
        .filter(
            Q(allowed_vehicle_kinds__id=vk_id)
            | Q(allowed_vehicle_rz__vehicle_kinds__id=vk_id)
        )
        .distinct()
        .order_by("last_name", "first_name", "personal_number")
    )
    if drive_date:
        drivers = drivers.exclude(pk__in=driver_ids_fully_absent_on_date(drive_date))
    driver = drivers.first()
    if not driver:
        return None, None
    rz_id = _pick_vehicle_rz_id_for_driver(driver, vehicle_kind_id=vk_id)
    return driver.pk, rz_id
