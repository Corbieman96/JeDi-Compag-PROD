"""Sestavení querysetu pro seznam průvodek (filtry podle role a optimalizace dotazů)."""

from __future__ import annotations

from typing import Any

from django.db.models import Prefetch

from waste_docs.models import Pruvodka, SvozTask


def pruvodka_list_optimized_qs() -> Any:
    return Pruvodka.objects.filter(is_archived=False).select_related("created_by", "activity").prefetch_related(
        "follow_up_children",
        Prefetch(
            "svoz_task_sources",
            queryset=SvozTask.objects.select_related("created_by").order_by("created_at"),
        ),
    )


def filter_pruvodka_list_queryset_for_user(qs: Any, user: Any) -> Any:
    """Každý s přístupem k seznamu vidí všechny nearchivované jízdy (přístup hlídá view)."""
    return qs
