from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from customer_requests.models import CustomerRequest
from reports.services.date_range import ReportDateRange, datetime_range_bounds
from reports.services.customer_requests_summary import build_customer_requests_summary
from reports.services.drivers_summary import build_drivers_summary
from reports.services.rides_summary import build_rides_summary
from reports.services.svoz_summary import build_svoz_summary
from reports.services.vehicle_repairs_summary import (
    build_vehicle_repairs_summary,
    format_hours,
)
from waste_docs.models import SvozTask


@dataclass(frozen=True)
class OperationsKpi:
    label: str
    value: str
    hint: str = ""


@dataclass
class OperationsSummary:
    kpis: list[OperationsKpi] = field(default_factory=list)
    rides_by_activity: list = field(default_factory=list)
    svoz_by_yard: list = field(default_factory=list)
    customer_requests_by_status: list = field(default_factory=list)


def build_operations_summary(date_range: ReportDateRange) -> OperationsSummary:
    rides = build_rides_summary(date_range)
    svoz = build_svoz_summary(date_range)
    drivers = build_drivers_summary(date_range)
    customer_requests = build_customer_requests_summary(date_range)
    repairs = build_vehicle_repairs_summary(date_range)

    today = timezone.localdate()
    svoz_queue = SvozTask.objects.filter(
        status=SvozTask.Status.OPEN,
        resolved_pruvodka__isnull=True,
        target_date__lte=today,
    ).count()

    start, end = datetime_range_bounds(date_range)
    cr_draft = CustomerRequest.objects.filter(
        created_at__gte=start,
        created_at__lte=end,
        status=CustomerRequest.Status.DRAFT,
    ).count()

    kpis = [
        OperationsKpi("Jízdy celkem", str(rides.total), f"{rides.generated_pct} % vygenerováno"),
        OperationsKpi("ZPO soubory", str(rides.zpo_generated_count), "Jízdy s vygenerovaným ZPO"),
        OperationsKpi("Návaznosti otevřené", str(rides.follow_up_open_count), "Průvodky s follow_up_open"),
        OperationsKpi("Bez řidiče / RZ", f"{rides.without_driver_count} / {rides.without_rz_count}", "V období"),
        OperationsKpi("Z požadavku zákazníka", str(rides.from_customer_request_count), "Propojené jízdy"),
        OperationsKpi("Svoz — fronta", str(svoz_queue), "Otevřené bez průvodky (≤ dnes)"),
        OperationsKpi("Svoz — dokončení", f"{svoz.completion_with_pruvodka_pct} %", "Vyřízené s průvodkou"),
        OperationsKpi("Požadavky nové", str(customer_requests.created_in_period), f"Konverze {customer_requests.conversion_to_ride_pct} %"),
        OperationsKpi("Fronta záloh", str(customer_requests.invoice_queue_count), "Aktuální stav"),
        OperationsKpi("Řidiči — jízdy/den", str(drivers.avg_rides_per_driver_day), "Průměr na řidič-den"),
        OperationsKpi("Řidič + absence", str(drivers.drivers_with_absence_and_rides), "Řidiči s jízdou i absencí"),
        OperationsKpi("Rozpracované požadavky", str(cr_draft), "Draft v období"),
        OperationsKpi(
            "Opravy — hodiny",
            format_hours(repairs.total_hours),
            f"{repairs.repair_count} záznamů v období",
        ),
        OperationsKpi(
            "Opravy — nejvíce opravované",
            repairs.top_vehicle_rz,
            f"{format_hours(repairs.top_vehicle_hours)} h v období",
        ),
    ]

    return OperationsSummary(
        kpis=kpis,
        rides_by_activity=rides.by_activity[:10],
        svoz_by_yard=svoz.by_yard[:10],
        customer_requests_by_status=customer_requests.by_status,
    )
