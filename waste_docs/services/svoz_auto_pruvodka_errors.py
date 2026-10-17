"""Záznam a čitelné důvody selhání auto-založení průvodky ze SvozTask."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone

from waste_docs.models import SvozTask

SKIP_REASON_LABELS: dict[str, str] = {
    "no_pair": "Chybí řádek matice (pár odpad–koncovka) pro auto-jízdu.",
    "no_plan": "Plán svozu nemá platné přiřazení řidiče a RZ pro auto-jízdu.",
    "no_auth": "Nelze založit jízdu: chybí přihlášený uživatel.",
    "no_permission": "Uživatel nemá oprávnění zakládat jízdy.",
    "not_open": "Úkol není otevřený nebo už má průvodku.",
    "no_driver": "Úkol nemá přiřazeného řidiče.",
    "no_activity": "Úkol nemá činnost — doplňte činnost v číselníku matice.",
    "active_ride": "Pro stejný kontejner a den už existuje aktivní jízda.",
    "no_vehicle_kind": "Chybí druh vozidla pro založení jízdy.",
    "form_invalid": "Formulář průvodky není platný.",
}


def label_for_skip_reason(code: str | None) -> str:
    if not code:
        return "Automatické založení jízdy selhalo."
    return SKIP_REASON_LABELS.get(code, code)


def record_auto_pruvodka_failure(task: SvozTask, message: str) -> str:
    """Uloží důvod na úkol (pro dashboard) a vrátí oříznutý text."""
    text = (message or "").strip() or "Automatické založení jízdy selhalo."
    text = text[:500]
    SvozTask.objects.filter(pk=task.pk).update(
        auto_pruvodka_last_error=text,
        auto_pruvodka_last_error_at=timezone.now(),
    )
    task.auto_pruvodka_last_error = text
    task.auto_pruvodka_last_error_at = timezone.now()
    return text


def clear_auto_pruvodka_failure(task: SvozTask) -> None:
    SvozTask.objects.filter(pk=task.pk).update(
        auto_pruvodka_last_error="",
        auto_pruvodka_last_error_at=None,
    )
    task.auto_pruvodka_last_error = ""
    task.auto_pruvodka_last_error_at = None


def pick_auto_pruvodka_fallback_actor(primary_user):
    """Dispečer/admin schopný založit jízdu, pokud účet SD ve formě selže."""
    from users.services.waste_doc_permissions import (
        can_create_pruvodka,
        can_see_all_waste_docs,
    )

    User = get_user_model()
    primary_pk = getattr(primary_user, "pk", None) if primary_user else None
    if (
        primary_user
        and getattr(primary_user, "is_authenticated", False)
        and can_see_all_waste_docs(primary_user)
        and can_create_pruvodka(primary_user)
    ):
        return None

    su = (
        User.objects.filter(is_active=True, is_superuser=True)
        .exclude(pk=primary_pk)
        .order_by("pk")
        .first()
    )
    if su:
        return su

    for user in (
        User.objects.filter(is_active=True)
        .exclude(pk=primary_pk)
        .order_by("pk")[:80]
    ):
        if can_see_all_waste_docs(user) and can_create_pruvodka(user):
            return user
    return None
