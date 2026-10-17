"""Řetězec návazností: mezikroky (Výměna) vs. uzavírací činnost (Stažení)."""

from __future__ import annotations

from catalogs.models import ActivityCatalog
from django.utils import timezone

from waste_docs.follow_up_options import has_follow_up_option
from waste_docs.models import Pruvodka


def _is_exchange_like_name(name: str) -> bool:
    label = (name or "").lower()
    return "výměna" in label or "vymena" in label


def terminal_follow_up_activity_ids(parent_activity) -> list[int]:
    """ID činností, které po propojení uzavřou follow_up_open u rodiče."""
    if not parent_activity:
        return []
    explicit = list(parent_activity.follow_up_terminal_activities.values_list("id", flat=True))
    allowed = parent_activity.follow_up_activity_ids_allowed()
    allowed_set = set(allowed)
    if explicit:
        return [aid for aid in explicit if aid in allowed_set]
    if len(allowed) == 1:
        return list(allowed)
    terminals: list[int] = []
    for act in ActivityCatalog.objects.filter(pk__in=allowed).only("pk", "name"):
        if not _is_exchange_like_name(act.name):
            terminals.append(act.pk)
    return terminals if terminals else list(allowed)


def child_closes_parent_follow_up(parent_activity, child_activity_id: int | None) -> bool:
    if not parent_activity or not child_activity_id:
        return False
    allowed = set(parent_activity.follow_up_activity_ids_allowed())
    if child_activity_id not in allowed:
        return False
    return child_activity_id in set(terminal_follow_up_activity_ids(parent_activity))


def parent_has_terminal_child(parent: Pruvodka) -> bool:
    if not parent.pk or not parent.activity_id:
        return False
    terminal_ids = set(terminal_follow_up_activity_ids(parent.activity))
    if not terminal_ids:
        return False
    return Pruvodka.objects.filter(
        follow_up_parent_id=parent.pk,
        is_archived=False,
        activity_id__in=terminal_ids,
    ).exists()


def parent_follow_up_should_stay_open(parent: Pruvodka) -> bool:
    if not parent.activity_id or not has_follow_up_option(parent.activity):
        return False
    return not parent_has_terminal_child(parent)


def apply_parent_state_after_child_link(parent: Pruvodka, child_activity_id: int | None) -> None:
    if not parent.pk:
        return
    if child_closes_parent_follow_up(parent.activity, child_activity_id):
        Pruvodka.objects.filter(pk=parent.pk, is_archived=False).update(
            follow_up_open=False,
            follow_up_resolved_at=timezone.now(),
        )
    else:
        Pruvodka.objects.filter(pk=parent.pk, is_archived=False).update(
            follow_up_open=True,
            follow_up_resolved_at=None,
        )


def sync_parent_follow_up_open_state(parent: Pruvodka) -> None:
    """Přepočet follow_up_open podle dětí (edit, archivace)."""
    if not parent.pk:
        return
    if parent_follow_up_should_stay_open(parent):
        Pruvodka.objects.filter(pk=parent.pk).update(
            follow_up_open=True,
            follow_up_resolved_at=None,
        )
        return
    now = timezone.now()
    Pruvodka.objects.filter(pk=parent.pk, follow_up_resolved_at__isnull=True).update(
        follow_up_open=False,
        follow_up_resolved_at=now,
    )
    Pruvodka.objects.filter(pk=parent.pk, follow_up_resolved_at__isnull=False).update(
        follow_up_open=False,
    )


def follow_up_wait_labels(parent_activity) -> tuple[list[str], list[str]]:
    """Názvy uzavíracích a mezikrokových činností pro UI."""
    if not parent_activity:
        return [], []
    allowed = parent_activity.follow_up_activity_ids_allowed()
    terminal_ids = set(terminal_follow_up_activity_ids(parent_activity))
    by_id = {
        act.pk: act.name
        for act in ActivityCatalog.objects.filter(pk__in=allowed).only("pk", "name")
    }
    terminal_names = [by_id[aid] for aid in allowed if aid in terminal_ids and aid in by_id]
    intermediate_names = [by_id[aid] for aid in allowed if aid not in terminal_ids and aid in by_id]
    return terminal_names, intermediate_names
