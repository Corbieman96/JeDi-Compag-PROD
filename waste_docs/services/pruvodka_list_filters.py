"""Společné filtry seznamu jízd (web i export) — jedna pravda pro výběr řádků."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.http import HttpRequest

from waste_docs.pruvodka_search import MAX_SEARCH_LEN, filter_pruvodka_queryset_by_search
from waste_docs.services.pruvodka_list_query import (
    filter_pruvodka_list_queryset_for_user,
    pruvodka_list_optimized_qs,
)


@dataclass
class PruvodkaListFilterState:
    selected_date: date | None
    date_from: date | None
    date_to: date | None
    awaiting_follow_up: bool
    blank_only: bool
    search_q: str


def parse_pruvodka_list_filter_request(request: HttpRequest) -> PruvodkaListFilterState:
    date_raw = (request.GET.get("date") or "").strip()
    date_from_raw = (request.GET.get("date_from") or "").strip()
    date_to_raw = (request.GET.get("date_to") or "").strip()
    awaiting = (request.GET.get("awaiting_follow_up") or "").strip() == "1"
    blank_only = (request.GET.get("blank_only") or "").strip() == "1"
    selected_date = None
    date_from = None
    date_to = None
    if date_raw:
        try:
            selected_date = date.fromisoformat(date_raw)
        except ValueError:
            selected_date = None
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
    return PruvodkaListFilterState(
        selected_date=selected_date,
        date_from=date_from,
        date_to=date_to,
        awaiting_follow_up=awaiting,
        blank_only=blank_only,
        search_q=search_q,
    )


def apply_pruvodka_list_filters(qs, state: PruvodkaListFilterState):
    if state.awaiting_follow_up:
        qs = qs.filter(follow_up_open=True)
    if state.blank_only:
        qs = qs.filter(is_blank_pruvodka=True, is_archived=False)
    if state.selected_date:
        qs = qs.filter(drive_date=state.selected_date)
    if state.date_from:
        qs = qs.filter(drive_date__gte=state.date_from)
    if state.date_to:
        qs = qs.filter(drive_date__lte=state.date_to)
    return filter_pruvodka_queryset_by_search(qs, state.search_q)


def get_pruvodka_list_queryset_for_request(request: HttpRequest, *, user: Any):
    """Vrátí odfiltrovaný QuerySet (řazení podle data jízdy, pak id) a stav filtrů z GET."""
    state = parse_pruvodka_list_filter_request(request)
    qs = filter_pruvodka_list_queryset_for_user(pruvodka_list_optimized_qs(), user)
    qs = apply_pruvodka_list_filters(qs, state)
    return qs.order_by("-drive_date", "-pk"), state
