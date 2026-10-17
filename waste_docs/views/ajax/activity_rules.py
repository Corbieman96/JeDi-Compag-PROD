from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse

from catalogs.models import ActivityCatalog
from waste_docs.activity_fields import activity_rules_for_json, effective_container_slot_count
from waste_docs.follow_up_options import has_follow_up_option


@login_required
def activity_field_rules_json(request):
    raw = (request.GET.get("activity_id") or "").strip()
    if not raw.isdigit():
        return JsonResponse(
            {
                "rules": activity_rules_for_json(None),
                "expects_follow_up": False,
                "can_complete_follow_up": False,
                "require_nitropodnikovy_subjekt": False,
                "container_slot_count": effective_container_slot_count(None),
            }
        )
    aid = int(raw)
    act = ActivityCatalog.objects.filter(pk=aid).select_related("follow_up_activity").first()
    can_complete = ActivityCatalog.objects.filter(Q(follow_up_activity_id=aid) | Q(follow_up_activities__id=aid)).exists()
    return JsonResponse(
        {
            "rules": activity_rules_for_json(aid),
            "expects_follow_up": has_follow_up_option(act),
            "can_complete_follow_up": can_complete,
            "require_nitropodnikovy_subjekt": bool(act and act.require_nitropodnikovy_subjekt),
            "container_slot_count": effective_container_slot_count(aid),
        }
    )
