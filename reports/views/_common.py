from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from reports.services.date_range import ReportDateRange, date_range_querystring


@dataclass(frozen=True)
class ReportCard:
    slug: str
    title: str
    description: str
    href: str
    kpi_hint: str = ""


def report_cards(date_range: ReportDateRange, *, hub_kpis: dict[str, str] | None = None) -> list[ReportCard]:
    qs = date_range_querystring(date_range)
    hub_kpis = hub_kpis or {}
    return [
        ReportCard(
            slug="operations",
            title="Provoz (souhrn)",
            description="Křížový přehled KPI — jízdy, svozy, požadavky a řidiči v jednom reportu.",
            href=f"{reverse('reports:operations')}?{qs}",
            kpi_hint=hub_kpis.get("operations", ""),
        ),
        ReportCard(
            slug="rides",
            title="Jízdy a průvodky",
            description="Počty jízd podle stavu, činnosti, druhu vozidla, řidiče, RZ a subjektu.",
            href=f"{reverse('reports:rides')}?{qs}",
            kpi_hint=hub_kpis.get("rides", ""),
        ),
        ReportCard(
            slug="suffix_workload",
            title="Vytížení koncovek",
            description="Koncovky celkem, páry koncovka/odpad, vytížení vozidel (RZ), export XLSX.",
            href=f"{reverse('reports:suffix_workload')}?{qs}",
            kpi_hint=hub_kpis.get("suffix_workload", ""),
        ),
        ReportCard(
            slug="drivers_day_rz",
            title="Vytížení řidičů (den / RZ)",
            description="Kdo který den jel kterou RZ — více vozidel za den pod sebou, export v XLSX listu Den RZ.",
            href=f"{reverse('reports:drivers')}?{qs}#day-rz",
            kpi_hint=hub_kpis.get("drivers", ""),
        ),
        ReportCard(
            slug="svoz",
            title="Svozové úkoly",
            description="Otevřené vs. dokončené úkoly ze sběrných dvorů, činnosti a druhy vozidel.",
            href=f"{reverse('reports:svoz')}?{qs}",
            kpi_hint=hub_kpis.get("svoz", ""),
        ),
        ReportCard(
            slug="drivers",
            title="Řidiči a absence",
            description="Jízdy na řidiče, vytížení den/RZ, průměr jízd/den, nepřítomnosti a export XLSX.",
            href=f"{reverse('reports:drivers')}?{qs}",
            kpi_hint=hub_kpis.get("drivers", ""),
        ),
        ReportCard(
            slug="customer_requests",
            title="Požadavky zákazníků",
            description="Nové požadavky, konverze na jízdu, činnosti a fronta záloh.",
            href=f"{reverse('reports:customer_requests')}?{qs}",
            kpi_hint=hub_kpis.get("customer_requests", ""),
        ),
        ReportCard(
            slug="print",
            title="Provoz tisku",
            description="Záznamy tisku podle uživatele a data jízdy.",
            href=f"{reverse('reports:print')}?{qs}",
            kpi_hint=hub_kpis.get("print", ""),
        ),
    ]


def report_context(request, date_range: ReportDateRange, *, title: str, active_slug: str) -> dict:
    return {
        "page_title": title,
        "active_report_slug": active_slug,
        "date_range": date_range,
        "reports_hub_url": reverse("reports:index"),
    }
