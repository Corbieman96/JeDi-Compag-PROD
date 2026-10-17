from __future__ import annotations

from dataclasses import dataclass

from customer_requests.models import CustomerRequest
from django.utils import timezone

from reports.services.date_range import ReportDateRange, datetime_range_bounds
from waste_docs.models import Pruvodka, PrintFileMark, SvozTask


@dataclass(frozen=True)
class HubSummary:
    rides_total: int = 0
    rides_generated_pct: float = 0.0
    svoz_open_in_period: int = 0
    svoz_unresolved_queue: int = 0
    customer_requests_created: int = 0
    invoice_queue_count: int = 0
    print_marks: int = 0
    driver_absences_overlap: int = 0


def build_hub_summary(date_range: ReportDateRange) -> HubSummary:
    from catalogs.models import DriverAbsence

    rides_qs = Pruvodka.objects.filter(
        drive_date__gte=date_range.date_from,
        drive_date__lte=date_range.date_to,
    )
    rides_total = rides_qs.count()
    generated = rides_qs.filter(status=Pruvodka.Status.GENERATED).count()
    generated_pct = round(100.0 * generated / rides_total, 1) if rides_total else 0.0

    svoz_qs = SvozTask.objects.filter(
        target_date__gte=date_range.date_from,
        target_date__lte=date_range.date_to,
    )
    svoz_open = svoz_qs.filter(status=SvozTask.Status.OPEN).count()
    today = timezone.localdate()
    svoz_queue = SvozTask.objects.filter(
        status=SvozTask.Status.OPEN,
        resolved_pruvodka__isnull=True,
        target_date__lte=today,
    ).count()

    start, end = datetime_range_bounds(date_range)
    cr_created = CustomerRequest.objects.filter(created_at__gte=start, created_at__lte=end).count()
    invoice_queue = CustomerRequest.objects.filter(
        status__in=(CustomerRequest.Status.SUBMITTED, CustomerRequest.Status.INVOICE_OVERDUE)
    ).count()

    print_marks = PrintFileMark.objects.filter(printed_at__gte=start, printed_at__lte=end).count()

    absences = DriverAbsence.objects.filter(
        date_from__lte=date_range.date_to,
        date_to__gte=date_range.date_from,
    ).count()

    return HubSummary(
        rides_total=rides_total,
        rides_generated_pct=generated_pct,
        svoz_open_in_period=svoz_open,
        svoz_unresolved_queue=svoz_queue,
        customer_requests_created=cr_created,
        invoice_queue_count=invoice_queue,
        print_marks=print_marks,
        driver_absences_overlap=absences,
    )


def hub_kpi_for_slug(slug: str, hub: HubSummary) -> str:
    mapping = {
        "rides": f"{hub.rides_total} jízd ({hub.rides_generated_pct} % vygener.)",
        "suffix_workload": f"{hub.rides_total} jízd v období",
        "svoz": f"{hub.svoz_open_in_period} otevřených · fronta {hub.svoz_unresolved_queue}",
        "drivers": f"{hub.driver_absences_overlap} absencí v období",
        "customer_requests": f"{hub.customer_requests_created} nových · fronta záloh {hub.invoice_queue_count}",
        "print": f"{hub.print_marks} tisků",
        "operations": f"{hub.rides_total} jízd · {hub.svoz_unresolved_queue} svozů ve frontě",
    }
    return mapping.get(slug, "")
