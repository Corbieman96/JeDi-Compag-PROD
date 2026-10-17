"""Výchozí časové okno seznamu jízd (/waste-docs/) — sdílená logika pro view i export."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from django.http import HttpRequest
from django.utils import timezone

from core.models import AppSettings
from waste_docs.services.pruvodka_list_filters import PruvodkaListFilterState


def default_range_days_from_settings() -> int:
    settings_obj = AppSettings.load()
    days = int(getattr(settings_obj, "waste_docs_default_range_days", 90) or 90)
    return min(max(days, 1), 365)


def resolve_list_date_range(
    request: HttpRequest,
    state: PruvodkaListFilterState,
    *,
    default_days: int | None = None,
) -> tuple[date | None, date | None, bool, bool]:
    """
    Vrátí (date_from, date_to, is_default_range, show_all).

    is_default_range: backend má aplikovat filtr období i bez explicitního GET date_from/date_to.
    show_all: ?all=1 — bez omezení data (kromě selected_date / awaiting / search).
    """
    if default_days is None:
        default_days = default_range_days_from_settings()

    show_all = (request.GET.get("all") or "").strip() == "1"
    explicit_from = bool((request.GET.get("date_from") or "").strip())
    explicit_to = bool((request.GET.get("date_to") or "").strip())
    has_explicit_range = explicit_from or explicit_to

    if show_all:
        return state.date_from, state.date_to, False, True

    if state.selected_date or has_explicit_range or state.awaiting_follow_up:
        return state.date_from, state.date_to, False, False

    session_last_date_to: date | None = None
    session_raw = (request.session.get("waste_docs_last_date_to") or "").strip()
    if session_raw:
        try:
            session_last_date_to = date.fromisoformat(session_raw)
        except ValueError:
            session_last_date_to = None

    date_to = session_last_date_to or timezone.localdate()
    date_from = date_to - timedelta(days=default_days)
    return date_from, date_to, True, False


def apply_effective_date_range_to_state(
    request: HttpRequest,
    state: PruvodkaListFilterState,
    *,
    default_days: int | None = None,
) -> tuple[PruvodkaListFilterState, bool, bool]:
    """Doplní state o výchozí rozsah; vrátí (state, is_default_range, show_all)."""
    date_from, date_to, is_default, show_all = resolve_list_date_range(
        request,
        state,
        default_days=default_days,
    )
    if is_default:
        state = PruvodkaListFilterState(
            selected_date=state.selected_date,
            date_from=date_from,
            date_to=date_to,
            awaiting_follow_up=state.awaiting_follow_up,
            blank_only=state.blank_only,
            search_q=state.search_q,
        )
    return state, is_default, show_all


def get_pruvodka_list_queryset_resolved(request: HttpRequest, *, user: Any):
    """QuerySet se stejným výchozím obdobím jako webový seznam (včetně 90 dní bez GET)."""
    from waste_docs.services.pruvodka_list_filters import (
        apply_pruvodka_list_filters,
        get_pruvodka_list_queryset_for_request,
    )
    from waste_docs.services.pruvodka_list_query import (
        filter_pruvodka_list_queryset_for_user,
        pruvodka_list_optimized_qs,
    )

    queryset, state = get_pruvodka_list_queryset_for_request(request, user=user)
    state, is_default_range, show_all = apply_effective_date_range_to_state(request, state)
    if is_default_range and (state.date_from or state.date_to):
        qs = filter_pruvodka_list_queryset_for_user(pruvodka_list_optimized_qs(), user)
        queryset = apply_pruvodka_list_filters(qs, state).order_by("-drive_date", "-pk")
    return queryset, state, is_default_range, show_all
