"""Filtr seznamu řidičů podle druhu vozidla — jedna pravda pro výběr řádků."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import QuerySet
from django.http import HttpRequest

from catalogs.models import DriverProfile, VehicleKindCatalog


@dataclass
class DriverListFilterState:
    vehicle_kind_id: int | None

    @property
    def has_filters(self) -> bool:
        return self.vehicle_kind_id is not None


def parse_driver_list_filter_request(request: HttpRequest) -> DriverListFilterState:
    raw = (request.GET.get("vehicle_kind") or "").strip()
    return DriverListFilterState(vehicle_kind_id=int(raw) if raw.isdigit() else None)


def filter_driver_list_queryset(state: DriverListFilterState) -> QuerySet:
    qs = DriverProfile.objects.prefetch_related("allowed_vehicle_rz__rz", "allowed_vehicle_kinds")
    if state.vehicle_kind_id is not None:
        qs = qs.filter(allowed_vehicle_kinds__pk=state.vehicle_kind_id).distinct()
    return qs


def driver_vehicle_kind_options() -> QuerySet:
    return VehicleKindCatalog.objects.order_by("sort_order", "name", "pk")
