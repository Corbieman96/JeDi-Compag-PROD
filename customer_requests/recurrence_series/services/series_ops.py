"""Výčet a úpravy výskytů opakované série."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_date_closure import target_date_closure_error
from waste_docs.services.customer_request_recurrence import (
    ensure_recurrence_occurrences,
    iter_recurrence_dates,
    parse_recurrence_weekdays,
    recurrence_series_root,
)

PROPAGATE_FIELDS = (
    "name_id",
    "activity_id",
    "vehicle_kind_id",
    "waste_type_id",
    "suffix_id",
    "address_id",
    "fulfillment_latitude",
    "fulfillment_longitude",
    "facility_address_snapshot",
    "contact_phone",
    "contact_note",
    "contract_number",
    "note",
)


def series_occurrences(root: CustomerRequest) -> list[CustomerRequest]:
    root = recurrence_series_root(root)
    children = list(
        root.recurrence_child_requests.select_related(
            "planned_pruvodka", "waste_type", "suffix", "activity", "vehicle_kind"
        ).order_by("target_date", "pk")
    )
    rows = [root] + children
    rows.sort(key=lambda r: (r.target_date or date.min, r.pk))
    return rows


def is_open_occurrence(item: CustomerRequest) -> bool:
    return (
        item.status == CustomerRequest.Status.VISIBLE_FOR_DISPATCH
        and not item.planned_pruvodka_id
    )


def partition_open_frozen(
    rows: list[CustomerRequest],
) -> tuple[list[CustomerRequest], list[CustomerRequest]]:
    open_rows: list[CustomerRequest] = []
    frozen: list[CustomerRequest] = []
    for row in rows:
        if is_open_occurrence(row):
            open_rows.append(row)
        else:
            frozen.append(row)
    return open_rows, frozen


def _cancel_occurrence(item: CustomerRequest, actor: AbstractBaseUser, note: str) -> None:
    item.status = CustomerRequest.Status.CANCELLED
    item.save(update_fields=["status", "updated_at"])
    log_customer_request_action(item, actor, "dispatcher_cancelled", note)


@transaction.atomic
def update_series_definition(
    root: CustomerRequest,
    *,
    weekdays_csv: str,
    until: date | None,
    actor: AbstractBaseUser,
) -> dict:
    """
    Aktualizuje metadata rodiče, zruší otevřené mimo novou sadu, doplní chybějící.
    Zmrazené nemění. Vrací counts.
    """
    root = recurrence_series_root(root)
    if root.recurrence_parent_request_id:
        raise ValueError("Definici série lze měnit jen na kořeni.")
    weekdays = parse_recurrence_weekdays(weekdays_csv)
    if not weekdays:
        raise ValueError("Vyberte alespoň jeden den v týdnu.")
    if until is None:
        raise ValueError("Vyplňte datum „do“.")

    root.recurrence_weekdays = ",".join(str(d) for d in sorted(weekdays))
    root.recurrence_until = until
    root.is_recurring = True
    root.save(
        update_fields=["recurrence_weekdays", "recurrence_until", "is_recurring", "updated_at"]
    )
    log_customer_request_action(
        root,
        actor,
        "fix_saved",
        f"Upravena pravidelnost série: {root.recurrence_weekdays}, do {until.isoformat()}.",
    )

    allowed = set(
        iter_recurrence_dates(root.target_date, until, root.recurrence_weekdays)
    )
    cancelled = 0
    for row in series_occurrences(root):
        if not is_open_occurrence(row):
            continue
        if row.target_date and row.target_date not in allowed:
            _cancel_occurrence(
                row,
                actor,
                f"Zrušeno — datum mimo novou pravidelnost série (kořen #{root.pk}).",
            )
            cancelled += 1

    created = ensure_recurrence_occurrences(root, actor)
    frozen_outside = [
        r
        for r in series_occurrences(root)
        if not is_open_occurrence(r)
        and r.status != CustomerRequest.Status.CANCELLED
        and r.target_date
        and r.target_date not in allowed
    ]
    return {
        "cancelled": cancelled,
        "created": len(created),
        "frozen_outside": len(frozen_outside),
    }


@transaction.atomic
def propagate_fields(
    root: CustomerRequest,
    actor: AbstractBaseUser,
    *,
    occurrence_ids: list[int] | None = None,
) -> int:
    """Kopíruje obsah z kořene na otevřené (nebo vybrané otevřené) výskyty."""
    root = recurrence_series_root(root)
    open_rows, _ = partition_open_frozen(series_occurrences(root))
    if occurrence_ids is not None:
        wanted = {int(x) for x in occurrence_ids}
        open_rows = [r for r in open_rows if r.pk in wanted]
    updated = 0
    for row in open_rows:
        changed = False
        for field in PROPAGATE_FIELDS:
            new_val = getattr(root, field)
            if getattr(row, field) != new_val:
                setattr(row, field, new_val)
                changed = True
        if changed:
            row.save(update_fields=[*PROPAGATE_FIELDS, "updated_at"])
            log_customer_request_action(
                row,
                actor,
                "fix_saved",
                f"Propagace obsahu ze série #{root.pk}.",
            )
            updated += 1
    return updated


@transaction.atomic
def shift_open_occurrences(
    root: CustomerRequest,
    delta_days: int,
    actor: AbstractBaseUser,
    *,
    occurrence_ids: list[int] | None = None,
) -> dict:
    """Posune target_date otevřených (nebo vybraných) o N dní."""
    root = recurrence_series_root(root)
    if delta_days == 0:
        return {"shifted": 0, "skipped": 0}
    open_rows, _ = partition_open_frozen(series_occurrences(root))
    if occurrence_ids is not None:
        wanted = {int(x) for x in occurrence_ids}
        open_rows = [r for r in open_rows if r.pk in wanted]
    shifted = 0
    skipped = 0
    for row in open_rows:
        if not row.target_date:
            skipped += 1
            continue
        new_day = row.target_date + timedelta(days=delta_days)
        err = target_date_closure_error(new_day, user=actor)
        if err:
            skipped += 1
            continue
        old = row.target_date
        row.target_date = new_day
        row.save(update_fields=["target_date", "updated_at"])
        log_customer_request_action(
            row,
            actor,
            "fix_saved",
            f"Posun termínu série #{root.pk}: {old.isoformat()} → {new_day.isoformat()}.",
        )
        shifted += 1
    return {"shifted": shifted, "skipped": skipped}
