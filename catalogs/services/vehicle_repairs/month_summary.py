"""Součet hodin oprav vozidla za zvolený měsíc."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import QuerySet, Sum
from django.utils import timezone

from catalogs.models import VehicleRzCatalog, VehicleRzRepair


def resolve_year_month(*, year: int | None = None, month: int | None = None) -> tuple[int, int]:
    today = timezone.localdate()
    y = int(year) if year else today.year
    m = int(month) if month else today.month
    if m < 1 or m > 12:
        m = today.month
    if y < 2000 or y > 2100:
        y = today.year
    return y, m


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def repairs_for_month(
    *,
    vehicle_rz: VehicleRzCatalog,
    year: int,
    month: int,
) -> QuerySet[VehicleRzRepair]:
    start, end = _month_bounds(year, month)
    return (
        VehicleRzRepair.objects.filter(
            vehicle_rz=vehicle_rz,
            repair_date__gte=start,
            repair_date__lte=end,
        )
        .select_related("created_by")
        .order_by("-repair_date", "-pk")
    )


def month_hours_sum(*, vehicle_rz: VehicleRzCatalog, year: int, month: int) -> Decimal:
    start, end = _month_bounds(year, month)
    total = (
        VehicleRzRepair.objects.filter(
            vehicle_rz=vehicle_rz,
            repair_date__gte=start,
            repair_date__lte=end,
        ).aggregate(s=Sum("hours"))["s"]
        or Decimal("0")
    )
    return total
