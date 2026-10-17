"""Rozbalení pravidelného požadavku na termíny (Po/Út … do data)."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from customer_requests.models import CustomerRequest
from waste_docs.forms.customer_request import WEEKDAY_CHOICES
from waste_docs.services.customer_request_audit import log_customer_request_action

_WEEKDAY_LABELS = {code: label for code, label in WEEKDAY_CHOICES}


def parse_recurrence_weekdays(raw: str | None) -> set[int]:
    out: set[int] = set()
    for part in (raw or "").split(","):
        text = part.strip()
        if not text:
            continue
        try:
            day = int(text)
        except ValueError:
            continue
        if 0 <= day <= 6:
            out.add(day)
    return out


def iter_recurrence_dates(
    start: date,
    until: date | None,
    weekdays_csv: str | None,
) -> list[date]:
    """Termíny včetně start (pokud padne na vybraný den), do until včetně."""
    weekdays = parse_recurrence_weekdays(weekdays_csv)
    from waste_docs.services.operating_calendar.resolve import resolve_operating_date

    if not weekdays or until is None or until < start:
        resolved = resolve_operating_date(start) if start else None
        return [resolved] if resolved else []
    out: list[date] = []
    seen: set[date] = set()
    cursor = start
    while cursor <= until:
        if cursor.weekday() in weekdays:
            resolved = resolve_operating_date(cursor)
            if resolved and resolved not in seen:
                seen.add(resolved)
                out.append(resolved)
        cursor += timedelta(days=1)
    return out


def format_recurrence_weekdays(weekdays_csv: str | None) -> str:
    labels: list[str] = []
    for part in (weekdays_csv or "").split(","):
        text = part.strip()
        if text in _WEEKDAY_LABELS:
            labels.append(_WEEKDAY_LABELS[text])
    return ", ".join(labels)


def format_recurrence_label(
    weekdays_csv: str | None,
    until: date | None,
) -> str:
    days = format_recurrence_weekdays(weekdays_csv)
    if not days:
        return ""
    if until:
        return f"{days} do {until.day}. {until.month}. {until.year}"
    return days


def recurrence_series_root(item: CustomerRequest) -> CustomerRequest:
    if item.recurrence_parent_request_id:
        return item.recurrence_parent_request
    return item


def recurrence_display_label(item: CustomerRequest) -> str:
    root = recurrence_series_root(item)
    if not root.is_recurring:
        return ""
    return format_recurrence_label(root.recurrence_weekdays, root.recurrence_until)


def _active_occurrence_dates(parent: CustomerRequest) -> set[date]:
    """Data výskytů, které blokují založení nového termínu (zrušené nepočítat)."""
    existing: set[date] = set()
    if parent.status != CustomerRequest.Status.CANCELLED and parent.target_date:
        existing.add(parent.target_date)
    existing.update(
        parent.recurrence_child_requests.exclude(
            status=CustomerRequest.Status.CANCELLED
        ).values_list("target_date", flat=True)
    )
    return existing


def can_expand_recurrence(item: CustomerRequest) -> bool:
    if item.recurrence_parent_request_id:
        return False
    if not item.is_recurring:
        return False
    if not parse_recurrence_weekdays(item.recurrence_weekdays):
        return False
    if item.recurrence_until is None:
        return False
    if item.status != CustomerRequest.Status.VISIBLE_FOR_DISPATCH:
        return False
    dates = iter_recurrence_dates(
        item.target_date, item.recurrence_until, item.recurrence_weekdays
    )
    existing = _active_occurrence_dates(item)
    return any(d not in existing for d in dates)


def _clone_occurrence(
    *,
    parent: CustomerRequest,
    target_date: date,
    actor: AbstractBaseUser,
) -> CustomerRequest:
    child = CustomerRequest(
        created_by=parent.created_by,
        name=parent.name,
        activity=parent.activity,
        vehicle_kind=parent.vehicle_kind,
        waste_type=parent.waste_type,
        suffix=parent.suffix,
        address=parent.address,
        fulfillment_latitude=parent.fulfillment_latitude,
        fulfillment_longitude=parent.fulfillment_longitude,
        facility_address_snapshot=parent.facility_address_snapshot,
        contact_phone=parent.contact_phone,
        contact_note=parent.contact_note,
        target_date=target_date,
        contract_number=parent.contract_number,
        note=parent.note,
        has_follow_up=False,
        follow_up_activity=None,
        follow_up_target_date=None,
        follow_up_parent_request=None,
        is_recurring=False,
        recurrence_weekdays="",
        recurrence_until=None,
        recurrence_parent_request=parent,
        requires_advance_invoice=False,
        advance_invoice_amount=None,
        invoice_due_date=None,
        status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        dispatcher_review_by=parent.dispatcher_review_by,
        dispatcher_reviewed_at=parent.dispatcher_reviewed_at,
        dispatcher_note=parent.dispatcher_note,
    )
    child.save()
    log_customer_request_action(
        child,
        actor,
        "create",
        f"Opakovaný termín {target_date.strftime('%d.%m.%Y')} ze série požadavku #{parent.pk}.",
    )
    return child


@transaction.atomic
def ensure_recurrence_occurrences(
    parent: CustomerRequest,
    actor: AbstractBaseUser,
) -> list[CustomerRequest]:
    """
    Doplní chybějící termíny série po schválení prvního požadavku.
    Idempotentní — existující data nepřepisuje.
    """
    if parent.recurrence_parent_request_id:
        return []
    if not parent.is_recurring:
        return []
    weekdays = parse_recurrence_weekdays(parent.recurrence_weekdays)
    if not weekdays or parent.recurrence_until is None:
        return []

    dates = iter_recurrence_dates(
        parent.target_date, parent.recurrence_until, parent.recurrence_weekdays
    )
    existing = _active_occurrence_dates(parent)
    created: list[CustomerRequest] = []
    for day in dates:
        if day in existing:
            continue
        created.append(_clone_occurrence(parent=parent, target_date=day, actor=actor))
        existing.add(day)

    if created:
        label = format_recurrence_label(parent.recurrence_weekdays, parent.recurrence_until)
        log_customer_request_action(
            parent,
            actor,
            "dispatcher_approved",
            f"Doplněno {len(created)} opakovaných termínů ({label}).",
        )
    return created
