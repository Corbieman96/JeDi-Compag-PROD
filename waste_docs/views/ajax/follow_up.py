from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from catalogs.models import ActivityCatalog
from users.services.access import can_see_all_waste_docs
from waste_docs.follow_up_prefill import build_follow_up_prefill
from waste_docs.models import Pruvodka


@login_required
def follow_up_candidates_json(request):
    raw = (request.GET.get("activity_id") or "").strip()
    include_closed = (request.GET.get("include_closed") or "").strip() in {"1", "true", "yes"}
    edit_item_raw = (request.GET.get("edit_item_id") or "").strip()
    edit_item_id = int(edit_item_raw) if edit_item_raw.isdigit() else None
    name_raw = (request.GET.get("name_id") or "").strip()
    name_id = int(name_raw) if name_raw.isdigit() else None
    query = (request.GET.get("q") or "").strip()
    if not raw.isdigit():
        return JsonResponse(
            {"candidates": [], "predecessor_activity_id": None, "predecessor_activity_ids": []}
        )
    aid = int(raw)
    if not ActivityCatalog.objects.filter(pk=aid).exists():
        return JsonResponse(
            {"candidates": [], "predecessor_activity_id": None, "predecessor_activity_ids": []}
        )
    preceding_ids = list(
        ActivityCatalog.objects.filter(Q(follow_up_activity_id=aid) | Q(follow_up_activities__id=aid))
        .values_list("pk", flat=True)
        .distinct()
    )
    if not preceding_ids:
        return JsonResponse(
            {
                "candidates": [],
                "predecessor_activity_id": None,
                "predecessor_activity_ids": [],
            }
        )
    qs = Pruvodka.objects.filter(activity_id__in=preceding_ids, is_archived=False)
    current_parent_id = None
    if include_closed and edit_item_id:
        edit_item = (
            Pruvodka.objects.filter(pk=edit_item_id, is_archived=False)
            .only("pk", "follow_up_parent_id", "name_id")
            .first()
        )
        if edit_item:
            current_parent_id = edit_item.follow_up_parent_id
            if not name_id:
                name_id = edit_item.name_id
            qs = qs.exclude(pk=edit_item.pk)
    if name_id:
        qs = qs.filter(name_id=name_id)
    if include_closed:
        allowed_filter = Q(follow_up_children__isnull=True)
        if current_parent_id:
            allowed_filter |= Q(pk=current_parent_id)
        qs = qs.filter(allowed_filter)
    else:
        qs = qs.filter(follow_up_open=True)
    if not can_see_all_waste_docs(request.user):
        qs = qs.filter(created_by=request.user)
    if query:
        q_obj = Q(name_snapshot__icontains=query)
        if query.isdigit():
            q_obj |= Q(pk=int(query))
        try:
            parsed_date = datetime.strptime(query, "%Y-%m-%d").date()
            q_obj |= Q(drive_date=parsed_date)
        except ValueError:
            pass
        try:
            parsed_date_cz = datetime.strptime(query, "%d.%m.%Y").date()
            q_obj |= Q(drive_date=parsed_date_cz)
        except ValueError:
            pass
        qs = qs.filter(q_obj)
    limit = 800 if include_closed else 80
    qs = qs.select_related("name").distinct().order_by("-drive_date", "-pk")[:limit]
    candidates = [
        {
            "pk": p.pk,
            "label": f"#{p.pk} — {p.name_snapshot or (p.name.value if p.name else '')} — {p.drive_date}",
            "drive_date": str(p.drive_date) if p.drive_date else "",
            "prefill": build_follow_up_prefill(p)["client"],
        }
        for p in qs
    ]
    pred_one = preceding_ids[0] if len(preceding_ids) == 1 else None
    return JsonResponse(
        {
            "candidates": candidates,
            "predecessor_activity_id": pred_one,
            "predecessor_activity_ids": list(preceding_ids),
        }
    )
