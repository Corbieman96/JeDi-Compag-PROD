"""Filtry a řazení seznamu požadavků (stav, fulltext)."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Case, IntegerField, Q, Value, When
from django.http import HttpRequest

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_fix.permissions import EDITABLE_STATUSES

MAX_SEARCH_LEN = 200


@dataclass
class CustomerRequestListFilterState:
    status_filter: str
    search_q: str


def parse_customer_request_list_filters(request: HttpRequest) -> CustomerRequestListFilterState:
    return CustomerRequestListFilterState(
        status_filter=(request.GET.get("status") or "").strip(),
        search_q=(request.GET.get("q") or "").strip()[:MAX_SEARCH_LEN],
    )


def apply_customer_request_list_filters(qs, state: CustomerRequestListFilterState):
    if state.status_filter:
        qs = qs.filter(status=state.status_filter)
    if not state.search_q:
        return qs
    q = state.search_q
    status_values = [
        value
        for value, label in CustomerRequest.Status.choices
        if q.lower() in label.lower() or q.lower() in value.lower()
    ]
    filters = (
        Q(name__value__icontains=q)
        | Q(activity__name__icontains=q)
        | Q(waste_type__value__icontains=q)
        | Q(waste_type__code__icontains=q)
        | Q(suffix__value__icontains=q)
        | Q(vehicle_kind__name__icontains=q)
        | Q(vehicle_kind__shortcut__icontains=q)
        | Q(contract_number__icontains=q)
        | Q(note__icontains=q)
        | Q(created_by__username__icontains=q)
        | Q(created_by__first_name__icontains=q)
        | Q(created_by__last_name__icontains=q)
    )
    if q.isdigit():
        filters |= Q(pk=int(q))
    if status_values:
        filters |= Q(status__in=status_values)
    return qs.filter(filters)


def apply_customer_request_list_ordering(qs):
    """Nejdřív položky k opravě (stejné stavy jako tlačítko Opravit), pak -created_at."""
    fix_first = Case(
        When(
            status__in=EDITABLE_STATUSES,
            planned_pruvodka_id__isnull=True,
            then=Value(0),
        ),
        default=Value(1),
        output_field=IntegerField(),
    )
    return qs.annotate(_list_fix_priority=fix_first).order_by("_list_fix_priority", "-created_at", "-pk")
