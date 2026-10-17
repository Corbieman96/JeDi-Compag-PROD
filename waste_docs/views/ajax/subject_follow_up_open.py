"""JSON: otevřené návaznosti (follow_up_open) průvodek daného subjektu (name_id)."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse

from catalogs.models import ActivityCatalog
from users.services.access import can_see_all_waste_docs
from waste_docs.follow_up_options import has_follow_up_option
from waste_docs.models import Pruvodka

_LIMIT_PLUS_ONE = 21


@login_required
def subject_open_follow_ups_json(request):
    raw = (request.GET.get("name_id") or "").strip()
    if not raw.isdigit():
        return JsonResponse({"items": [], "count": 0, "has_more": False})
    name_id = int(raw)
    qs = (
        Pruvodka.objects.filter(name_id=name_id, follow_up_open=True, is_archived=False)
        .select_related("activity", "activity__follow_up_activity")
        .prefetch_related("activity__follow_up_activities")
        .order_by("-drive_date", "-pk")
    )
    activity_raw = (request.GET.get("activity_id") or "").strip()
    if activity_raw.isdigit():
        aid = int(activity_raw)
        preceding_ids = list(
            ActivityCatalog.objects.filter(
                Q(follow_up_activity_id=aid) | Q(follow_up_activities__id=aid)
            )
            .values_list("pk", flat=True)
            .distinct()
        )
        if not preceding_ids:
            return JsonResponse({"items": [], "count": 0, "has_more": False})
        qs = qs.filter(activity_id__in=preceding_ids)
    if not can_see_all_waste_docs(request.user):
        qs = qs.filter(created_by=request.user)
    rows = [p for p in qs[:_LIMIT_PLUS_ONE] if has_follow_up_option(p.activity)]
    has_more = len(rows) > 20
    rows = rows[:20]
    items = [
        {
            "pk": p.pk,
            "drive_date": str(p.drive_date) if p.drive_date else "",
            "activity_name": (p.activity.name if p.activity_id and p.activity else "") or "",
            "detail_url": reverse("waste_docs:detail", args=[p.pk]),
        }
        for p in rows
    ]
    return JsonResponse({"items": items, "count": len(items), "has_more": has_more})
