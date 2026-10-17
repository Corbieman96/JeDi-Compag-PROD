"""Počty jízd za den podle druhu vozidla (Řetěz / Atego / Hák) pro stránku nové jízdy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import profile_vehicle_kind_ids
from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.vehicle_kind_day_buckets import (
    BUCKET_LABELS,
    BUCKET_ORDER,
    bucket_for_kind_ids,
    bucket_kind_id_sets,
)


@dataclass(frozen=True)
class DayKindCountRow:
    key: str
    label: str
    count: int


@dataclass(frozen=True)
class DayKindCountSummary:
    date: date
    rows: tuple[DayKindCountRow, ...]
    total: int
    unclassified: int

    @property
    def classified_total(self) -> int:
        return sum(row.count for row in self.rows)


def kind_ids_for_ride(ride, profile) -> set[int]:
    kind_ids = profile_vehicle_kind_ids(profile)
    if kind_ids:
        return kind_ids
    driver = getattr(ride, "driver", None)
    if not driver or not driver.pk:
        return set()
    prefetched = getattr(driver, "_prefetched_objects_cache", {}).get("allowed_vehicle_kinds")
    if prefetched is not None:
        return {int(k.pk) for k in prefetched}
    return {int(k) for k in driver.allowed_vehicle_kinds.values_list("pk", flat=True)}


def ride_counts_by_vehicle_kind_bucket(user: AbstractBaseUser, day: date) -> DayKindCountSummary:
    """
    Počty běžných (ne bianko) nearchivovaných jízd za den podle druhu vozidla.

    Druh: profil RZ → fallback povolené druhy u řidiče.
    Každá jízda nejvýše jednou — priorita: Řetěz → Atego → Hák.
    """
    bucket_sets = bucket_kind_id_sets()

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

    counts = {key: 0 for key in BUCKET_ORDER}
    for ride in rides:
        prof = profile_by_rz.get(ride.vehicle_rz_id) if ride.vehicle_rz_id else None
        kind_ids = kind_ids_for_ride(ride, prof)
        bucket = bucket_for_kind_ids(kind_ids, bucket_sets)
        if bucket:
            counts[bucket] += 1

    total = len(rides)
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


__all__ = [
    "DayKindCountRow",
    "DayKindCountSummary",
    "kind_ids_for_ride",
    "ride_counts_by_vehicle_kind_bucket",
]
