"""Počty jízd, požadavků a řidičů za den podle druhu vozidla — modal na detailu požadavku."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.utils.formats import date_format

from catalogs.models import VehicleRzProfile
from customer_requests.models import CustomerRequest
from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_day_kind_counts import (
    DayKindCountRow,
    DayKindCountSummary,
    kind_ids_for_ride,
    ride_counts_by_vehicle_kind_bucket,
)
from waste_docs.services.vehicle_kind_day_buckets import (
    BUCKET_LABELS,
    BUCKET_ORDER,
    bucket_for_kind_ids,
    bucket_kind_id_sets,
)

_OPEN_CUSTOMER_REQUEST_STATUSES = frozenset(
    {
        CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        CustomerRequest.Status.DISPATCHER_REVIEW,
        CustomerRequest.Status.REQUIRES_RESCHEDULE,
        CustomerRequest.Status.SUBMITTED,
        CustomerRequest.Status.INVOICE_OVERDUE,
        CustomerRequest.Status.RETURNED_FOR_FIX,
    }
)


def parse_modal_date(raw: str | None, *, default: date) -> date | None:
    text = (raw or "").strip()
    if not text:
        return default
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def resolve_day_for_customer_request(
    cr: CustomerRequest,
    raw_date: str | None,
) -> date | None:
    return parse_modal_date(raw_date, default=cr.target_date)


def _rides_for_day(user: AbstractBaseUser, day: date):
    rides_qs = Pruvodka.objects.filter(
        drive_date=day,
        is_archived=False,
        is_blank_pruvodka=False,
    )
    if not can_see_all_waste_docs(user):
        rides_qs = rides_qs.filter(created_by=user)
    rides = list(
        rides_qs.select_related("vehicle_rz__profile", "driver").prefetch_related(
            "driver__allowed_vehicle_kinds"
        ).only(
            "pk",
            "vehicle_rz_id",
            "driver_id",
        )
    )
    rz_ids = {ride.vehicle_rz_id for ride in rides if ride.vehicle_rz_id}
    profile_by_rz: dict[int, VehicleRzProfile] = {}
    if rz_ids:
        profiles = VehicleRzProfile.objects.filter(rz_id__in=rz_ids).prefetch_related("vehicle_kinds")
        profile_by_rz = {prof.rz_id: prof for prof in profiles}
    return rides, profile_by_rz


def driver_counts_on_rides_by_vehicle_kind_bucket(
    user: AbstractBaseUser,
    day: date,
) -> DayKindCountSummary:
    """Počet distinct řidičů na jízdách za den podle druhu vozidla (Řetěz / Atego / Hák)."""
    bucket_sets = bucket_kind_id_sets()
    rides, profile_by_rz = _rides_for_day(user, day)

    drivers_per_bucket: dict[str, set[int]] = {key: set() for key in BUCKET_ORDER}
    all_drivers: set[int] = set()
    classified_drivers: set[int] = set()

    for ride in rides:
        if not ride.driver_id:
            continue
        driver_id = int(ride.driver_id)
        all_drivers.add(driver_id)
        prof = profile_by_rz.get(ride.vehicle_rz_id) if ride.vehicle_rz_id else None
        kind_ids = kind_ids_for_ride(ride, prof)
        bucket = bucket_for_kind_ids(kind_ids, bucket_sets)
        if bucket:
            drivers_per_bucket[bucket].add(driver_id)
            classified_drivers.add(driver_id)

    rows = tuple(
        DayKindCountRow(key=key, label=BUCKET_LABELS[key], count=len(drivers_per_bucket[key]))
        for key in BUCKET_ORDER
    )
    return DayKindCountSummary(
        date=day,
        rows=rows,
        total=len(all_drivers),
        unclassified=max(0, len(all_drivers) - len(classified_drivers)),
    )


def customer_request_counts_by_vehicle_kind_bucket(day: date) -> DayKindCountSummary:
    """Počty otevřených požadavků za den podle druhu vozidla (Řetěz / Atego / Hák)."""
    bucket_sets = bucket_kind_id_sets()
    requests = list(
        CustomerRequest.objects.filter(
            target_date=day,
            status__in=_OPEN_CUSTOMER_REQUEST_STATUSES,
        )
        .only("pk", "vehicle_kind_id")
        .order_by("pk")
    )

    counts = {key: 0 for key in BUCKET_ORDER}
    for item in requests:
        if not item.vehicle_kind_id:
            continue
        bucket = bucket_for_kind_ids({int(item.vehicle_kind_id)}, bucket_sets)
        if bucket:
            counts[bucket] += 1

    total = len(requests)
    rows = tuple(
        DayKindCountRow(key=key, label=BUCKET_LABELS[key], count=counts[key])
        for key in BUCKET_ORDER
    )
    classified = sum(counts.values())
    return DayKindCountSummary(
        date=day,
        rows=rows,
        total=total,
        unclassified=max(0, total - classified),
    )


def _section_payload(key: str, label: str, summary: DayKindCountSummary) -> dict:
    return {
        "key": key,
        "label": label,
        "counts": [row.count for row in summary.rows],
        "total": summary.total,
        "unclassified": summary.unclassified,
    }


def build_day_kind_counts_modal_payload(user: AbstractBaseUser, day: date) -> dict:
    rides = ride_counts_by_vehicle_kind_bucket(user, day)
    requests = customer_request_counts_by_vehicle_kind_bucket(day)
    drivers = driver_counts_on_rides_by_vehicle_kind_bucket(user, day)
    return {
        "date": day.isoformat(),
        "date_display": date_format(day, format="l j. n. Y", use_l10n=True),
        "bucket_labels": [BUCKET_LABELS[key] for key in BUCKET_ORDER],
        "sections": [
            _section_payload("rides", "Jízdy", rides),
            _section_payload("requests", "Požadavky", requests),
            _section_payload("drivers", "Řidiči", drivers),
        ],
    }


__all__ = [
    "build_day_kind_counts_modal_payload",
    "customer_request_counts_by_vehicle_kind_bucket",
    "driver_counts_on_rides_by_vehicle_kind_bucket",
    "parse_modal_date",
    "resolve_day_for_customer_request",
]
