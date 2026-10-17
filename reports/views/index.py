from __future__ import annotations

from django.shortcuts import render

from reports.services.date_range import parse_date_range_from_request
from reports.services.hub_summary import build_hub_summary, hub_kpi_for_slug
from reports.views._common import report_cards, report_context
from reports.views.period_digest import period_digest_card
from core.services.reports.period_txt_digest import user_can_period_txt_digest


def index(request):
    date_range = parse_date_range_from_request(request)
    hub = build_hub_summary(date_range)
    hub_kpis = {card_slug: hub_kpi_for_slug(card_slug, hub) for card_slug in (
        "operations", "rides", "suffix_workload", "svoz", "drivers", "customer_requests", "print"
    )}
    ctx = report_context(request, date_range, title="Reporty", active_slug="")
    ctx["hub"] = hub
    cards = list(report_cards(date_range, hub_kpis=hub_kpis))
    if user_can_period_txt_digest(request.user):
        cards.append(period_digest_card(date_range))
    ctx["cards"] = cards
    return render(request, "reports/index.html", ctx)
