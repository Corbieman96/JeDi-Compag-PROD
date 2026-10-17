"""Filtry seznamu smazaných jízd — sdílené pro view a případný export."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q

from waste_docs.models import PruvodkaSoftDeleteLog
from waste_docs.pruvodka_search import MAX_SEARCH_LEN


@dataclass
class SoftDeleteLogFilterState:
    date_from: date | None
    date_to: date | None
    search_q: str


def parse_soft_delete_log_filter_request(request) -> SoftDeleteLogFilterState:
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()
    date_from = None
    date_to = None
    if date_from_raw:
        try:
            date_from = date.fromisoformat(date_from_raw)
        except ValueError:
            date_from = None
    if date_to_raw:
        try:
            date_to = date.fromisoformat(date_to_raw)
        except ValueError:
            date_to = None
    search_q = (request.GET.get("q") or "").strip()[:MAX_SEARCH_LEN]
    return SoftDeleteLogFilterState(
        date_from=date_from,
        date_to=date_to,
        search_q=search_q,
    )


def soft_delete_log_queryset() -> Any:
    return PruvodkaSoftDeleteLog.objects.select_related("deleted_by", "pruvodka")


def apply_soft_delete_log_filters(qs: Any, state: SoftDeleteLogFilterState) -> Any:
    if state.date_from:
        qs = qs.filter(deleted_at__date__gte=state.date_from)
    if state.date_to:
        qs = qs.filter(deleted_at__date__lte=state.date_to)
    term = (state.search_q or "").strip()
    if term:
        qs = qs.filter(
            Q(snd_cislo_listu__icontains=term)
            | Q(name_snapshot__icontains=term)
            | Q(vehicle_rz_snapshot__icontains=term)
            | Q(driver_snapshot__icontains=term)
            | Q(activity_snapshot__icontains=term)
            | Q(reason__icontains=term)
            | Q(deleted_by__username__icontains=term)
            | Q(deleted_by__last_name__icontains=term)
            | Q(deleted_by__first_name__icontains=term)
        )
    return qs
