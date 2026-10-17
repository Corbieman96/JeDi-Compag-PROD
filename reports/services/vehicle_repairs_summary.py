"""Souhrn oprav vozidel pro reporty (období date_from–date_to)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from catalogs.models import VehicleRzRepair
from reports.services.date_range import ReportDateRange


@dataclass(frozen=True)
class VehicleRepairsSummary:
    total_hours: Decimal
    repair_count: int
    top_vehicle_rz: str
    top_vehicle_hours: Decimal


def build_vehicle_repairs_summary(date_range: ReportDateRange) -> VehicleRepairsSummary:
    qs = VehicleRzRepair.objects.filter(
        repair_date__gte=date_range.date_from,
        repair_date__lte=date_range.date_to,
    )
    total_hours = qs.aggregate(s=Sum("hours"))["s"] or Decimal("0")
    repair_count = qs.count()

    top = (
        qs.values("vehicle_rz_id", "vehicle_rz__value")
        .annotate(hours=Sum("hours"), cnt=Count("id"))
        .order_by("-hours", "-cnt", "vehicle_rz__value")
        .first()
    )
    if not top:
        return VehicleRepairsSummary(
            total_hours=total_hours,
            repair_count=repair_count,
            top_vehicle_rz="—",
            top_vehicle_hours=Decimal("0"),
        )
    return VehicleRepairsSummary(
        total_hours=total_hours,
        repair_count=repair_count,
        top_vehicle_rz=(top.get("vehicle_rz__value") or "—").strip() or "—",
        top_vehicle_hours=top.get("hours") or Decimal("0"),
    )


def format_hours(value: Decimal) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text or "0"
