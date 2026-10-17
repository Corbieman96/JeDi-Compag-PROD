"""Uzavření kalendářních dnů pro nové zákaznické požadavky — auto cutoff a ruční přepínač."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from customer_requests.models import CustomerRequestDateClosure
from users.constants import ROLE_ADMIN
from users.services.access import app_role, can_see_all_waste_docs

# Prohlížečový setTimeout zvládne max ~24,8 dne; delší delay se přetočí a reloaduje dokola.
_AUTO_UI_REFRESH_MIN = timedelta(seconds=2)
_AUTO_UI_REFRESH_MAX = timedelta(hours=12)


def auto_cutoff_time() -> time | None:
    from core.models import AppSettings

    try:
        value = AppSettings.load().customer_request_daily_cutoff_time
    except Exception:
        return None
    return value


def can_bypass_date_closure(user: AbstractBaseUser | None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return app_role(user) == ROLE_ADMIN


def deadline_for_day(day: date) -> datetime | None:
    """Nejzazší okamžik, kdy lze zadat požadavek na `day` (deadline = předchozí den v cutoff)."""
    cutoff = auto_cutoff_time()
    if cutoff is None:
        return None
    naive = datetime.combine(day - timedelta(days=1), cutoff)
    return timezone.make_aware(naive)


def is_auto_closed(day: date, *, now: datetime | None = None) -> bool:
    """Automatické uzavření je monotónní: jakmile deadline dne uplyne, zůstává uzavřeno."""
    deadline = deadline_for_day(day)
    if deadline is None:
        return False
    return timezone.localtime(now) >= deadline


def _manual_override(day: date) -> CustomerRequestDateClosure | None:
    return CustomerRequestDateClosure.objects.filter(closure_date=day).first()


def is_manually_closed(day: date) -> bool:
    row = _manual_override(day)
    return bool(row and row.is_closed)


def is_target_date_closed(day: date | None, *, now: datetime | None = None) -> bool:
    if not day:
        return False
    row = _manual_override(day)
    if row is not None:
        # Ruční nastavení má přednost před automatem (uzavřít i znovu otevřít).
        return row.is_closed
    return is_auto_closed(day, now=now)


def target_date_closure_error(
    day: date | None,
    *,
    user: AbstractBaseUser | None = None,
    now: datetime | None = None,
) -> str | None:
    if not day or can_bypass_date_closure(user):
        return None
    now = timezone.localtime(now)
    row = _manual_override(day)
    if row is not None:
        if row.is_closed:
            return "Pro tento den bylo zadávání požadavků uzavřeno dispečerem."
        return None
    if is_auto_closed(day, now=now):
        cutoff = auto_cutoff_time()
        label = cutoff.strftime("%H:%M") if cutoff else "?"
        earliest = _first_open_date_from(now)
        return (
            f"Zadávání požadavků na tento den je již uzavřeno (uzávěrka byla den předem "
            f"v {label}). Nejbližší možný termín je {earliest.strftime('%d.%m.%Y')}."
        )
    return None


def _is_operating_day(day: date) -> bool:
    from waste_docs.services.operating_calendar.resolve import is_operating_day

    return is_operating_day(day)


def _first_open_date_from(now: datetime, *, max_days: int = 366) -> date:
    """První den od dneška, kdy není uzavřeno (automat ani ruční záznam v DB)."""
    today = timezone.localdate(now)
    for offset in range(max_days):
        day = today + timedelta(days=offset)
        if not is_target_date_closed(day, now=now) and _is_operating_day(day):
            return day
    return today + timedelta(days=max_days - 1)


def toggle_manual_closure(
    user: AbstractBaseUser, day: date, *, now: datetime | None = None
) -> bool:
    """Přepne efektivní stav dne (vč. přebití automatu); vrátí nový stav is_closed."""
    new_state = not is_target_date_closed(day, now=now)
    row, _created = CustomerRequestDateClosure.objects.get_or_create(
        closure_date=day,
        defaults={"is_closed": new_state, "updated_by": user},
    )
    if not _created:
        row.is_closed = new_state
        row.updated_by = user
        row.save(update_fields=["is_closed", "updated_by", "updated_at"])
    return row.is_closed


@dataclass(frozen=True)
class DashboardClosureContext:
    is_closed: bool
    is_auto: bool
    is_manual: bool
    can_toggle: bool
    cutoff_label: str | None
    toggle_label: str
    status_note: str
    status_label: str
    # ISO deadline: když je den ještě otevřený jen díky autu, UI se po tomto čase obnoví.
    auto_ui_refresh_at: str | None = None


def dashboard_closure_context(
    day: date,
    *,
    user: AbstractBaseUser | None = None,
    now: datetime | None = None,
) -> DashboardClosureContext:
    now = timezone.localtime(now)
    can_toggle = bool(user and user.is_authenticated and can_see_all_waste_docs(user))
    auto = is_auto_closed(day, now=now)
    override = _manual_override(day)
    closed = override.is_closed if override is not None else auto
    cutoff = auto_cutoff_time()
    cutoff_label = cutoff.strftime("%H:%M") if cutoff else None

    toggle_label = "Požadavky: otevřít" if closed else "Požadavky: uzavřít"
    date_suffix = f" ({day.day}. {day.month}.)"
    status_label = ("Požadavky uzavřeny" if closed else "Požadavky otevřeny") + date_suffix

    notes: list[str] = []
    if override is not None:
        if override.is_closed and not auto:
            notes.append("ručně uzavřeno dispečerem")
        elif not override.is_closed and auto:
            notes.append("ručně znovu otevřeno dispečerem")
        elif override.is_closed:
            notes.append("uzavřeno dispečerem")
    elif auto and cutoff_label:
        notes.append(f"automaticky uzavřeno (uzávěrka {cutoff_label})")
    status_note = " · ".join(notes)

    # Stale dashboard: po cutoff obnovit stránku, ať tlačítko ukáže auto-uzavření.
    # Jen když uzávěrka nastane brzy — vzdálené dny (13.9., 11.11.) nesmí dostat setTimeout.
    auto_ui_refresh_at: str | None = None
    if override is None and not closed:
        deadline = deadline_for_day(day)
        if deadline is not None:
            deadline_local = timezone.localtime(deadline)
            delta = deadline_local - now
            if _AUTO_UI_REFRESH_MIN <= delta <= _AUTO_UI_REFRESH_MAX:
                auto_ui_refresh_at = deadline_local.isoformat()

    return DashboardClosureContext(
        is_closed=closed,
        is_auto=auto,
        is_manual=bool(override and override.is_closed),
        can_toggle=can_toggle,
        cutoff_label=cutoff_label,
        toggle_label=toggle_label,
        status_note=status_note,
        status_label=status_label,
        auto_ui_refresh_at=auto_ui_refresh_at,
    )


def target_date_min_for_user(user: AbstractBaseUser | None, *, now: datetime | None = None) -> date | None:
    """Nejdřívější povolené datum pro nový požadavek (UX v date pickeru)."""
    if can_bypass_date_closure(user):
        return None
    now = timezone.localtime(now)
    cutoff = auto_cutoff_time()
    if cutoff is None:
        return None
    return _first_open_date_from(now)


__all__ = [
    "DashboardClosureContext",
    "auto_cutoff_time",
    "can_bypass_date_closure",
    "dashboard_closure_context",
    "is_auto_closed",
    "is_manually_closed",
    "is_target_date_closed",
    "target_date_closure_error",
    "target_date_min_for_user",
    "toggle_manual_closure",
]
