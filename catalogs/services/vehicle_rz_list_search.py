"""Filtrování seznamu RZ vozidel podle textového dotazu."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from catalogs.models import VehicleRzProfile


def filter_vehicle_rz_profiles(qs: QuerySet[VehicleRzProfile], query: str) -> QuerySet[VehicleRzProfile]:
    text = (query or "").strip()
    if not text:
        return qs
    return qs.filter(Q(rz__value__icontains=text) | Q(vehicle_type__icontains=text))
