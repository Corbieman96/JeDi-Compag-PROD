"""Kontext pro dashboard: uzávěrka druhů vozidel (tlačítko + modal)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import AbstractBaseUser

from catalogs.models import VehicleKindCatalog
from customer_requests.models import CustomerRequestVehicleKindClosure
from users.services.access import can_see_all_waste_docs


@dataclass(frozen=True)
class KindClosureChip:
    kind_id: int
    shortcut: str
    label: str
    is_closed: bool
    title: str


def dashboard_kind_closure_context(
    day: date,
    *,
    user: AbstractBaseUser | None = None,
) -> dict:
    can_toggle = bool(user and user.is_authenticated and can_see_all_waste_docs(user))
    closed_ids = set(
        CustomerRequestVehicleKindClosure.objects.filter(
            closure_date=day,
            is_closed=True,
        ).values_list("vehicle_kind_id", flat=True)
    )
    chips: list[KindClosureChip] = []
    closed_shortcuts: list[str] = []
    for kind in VehicleKindCatalog.objects.order_by("sort_order", "name", "pk"):
        closed = kind.pk in closed_ids
        sc = (kind.shortcut or "").strip() or "?"
        label = kind.display_label()
        if closed:
            closed_shortcuts.append(sc)
            title = f"Uzavřeno — kliknutím znovu otevřít ({label})"
        else:
            title = f"Otevřeno — kliknutím uzavřít ({label})"
        chips.append(
            KindClosureChip(
                kind_id=kind.pk,
                shortcut=sc,
                label=label,
                is_closed=closed,
                title=title,
            )
        )
    closed_shortcuts_label = ", ".join(closed_shortcuts)
    if closed_shortcuts_label:
        button_title = f"Uzamčeno: {closed_shortcuts_label}"
        button_label = f"Druhy ({len(closed_shortcuts)})"
    else:
        button_title = "Žádný druh není uzamčen — kliknutím otevřete správu"
        button_label = "Druhy"
    return {
        "can_toggle": can_toggle,
        "chips": chips,
        "has_any_closed": bool(closed_ids),
        "closed_shortcuts": closed_shortcuts_label,
        "button_title": button_title,
        "button_label": button_label,
        "day_iso": day.isoformat(),
        "day_label": day.strftime("%d.%m.%Y"),
    }


__all__ = ["KindClosureChip", "dashboard_kind_closure_context"]
