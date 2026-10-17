"""Soft-cancel otevřených výskytů série (vše / vybrané / rozsah od–do)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from customer_requests.models import CustomerRequest
from customer_requests.recurrence_series.services.series_ops import (
    is_open_occurrence,
    series_occurrences,
)
from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_recurrence import recurrence_series_root


def _cancel_one(item: CustomerRequest, actor: AbstractBaseUser, reason: str) -> None:
    item.status = CustomerRequest.Status.CANCELLED
    item.save(update_fields=["status", "updated_at"])
    log_customer_request_action(item, actor, "dispatcher_cancelled", reason)


@transaction.atomic
def cancel_open_occurrences(
    root: CustomerRequest,
    actor: AbstractBaseUser,
    *,
    reason: str,
    from_date: date | None = None,
    occurrence_ids: list[int] | None = None,
) -> list[CustomerRequest]:
    """
    Zruší otevřené výskyty:
    - occurrence_ids: jen vybrané (musí být otevřené),
    - jinak všechny otevřené, volitelně od from_date včetně.
    """
    root = recurrence_series_root(root)
    reason = (reason or "").strip() or "Zrušeno ze správy série."
    cancelled: list[CustomerRequest] = []
    open_rows = [r for r in series_occurrences(root) if is_open_occurrence(r)]

    if occurrence_ids is not None:
        wanted = {int(x) for x in occurrence_ids}
        targets = [r for r in open_rows if r.pk in wanted]
    else:
        targets = open_rows
        if from_date is not None:
            targets = [r for r in targets if r.target_date and r.target_date >= from_date]

    for row in targets:
        note = f"{reason} (série #{root.pk})"
        _cancel_one(row, actor, note)
        cancelled.append(row)

    if cancelled:
        log_customer_request_action(
            root,
            actor,
            "dispatcher_cancelled",
            f"Hromadné zrušení {len(cancelled)} otevřených termínů. {reason}",
        )
    return cancelled


@transaction.atomic
def cancel_series_range(
    root: CustomerRequest,
    actor: AbstractBaseUser,
    *,
    from_date: date,
    to_date: date,
    reason: str,
) -> list[CustomerRequest]:
    """Soft-cancel otevřených s target_date v [from_date, to_date]."""
    root = recurrence_series_root(root)
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Důvod zrušení je povinný.")
    if from_date > to_date:
        raise ValueError("Datum „od“ musí být před nebo stejné jako „do“.")

    cancelled: list[CustomerRequest] = []
    for row in series_occurrences(root):
        if not is_open_occurrence(row):
            continue
        if not row.target_date or row.target_date < from_date or row.target_date > to_date:
            continue
        _cancel_one(row, actor, f"{reason} (série #{root.pk}, rozsah {from_date}–{to_date})")
        cancelled.append(row)

    if cancelled:
        log_customer_request_action(
            root,
            actor,
            "dispatcher_cancelled",
            f"Zrušeno {len(cancelled)} termínů v rozsahu {from_date}–{to_date}. {reason}",
        )
    return cancelled
