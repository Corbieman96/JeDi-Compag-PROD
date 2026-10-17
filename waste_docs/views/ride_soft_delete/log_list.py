from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from waste_docs.services.ride_soft_delete.log_filters import (
    apply_soft_delete_log_filters,
    parse_soft_delete_log_filter_request,
    soft_delete_log_queryset,
)
from waste_docs.services.ride_soft_delete.permissions import can_view_soft_delete_log
from waste_docs.views.access import waste_docs_list_access_required


@waste_docs_list_access_required
def ride_soft_delete_log_list(request):
    if not can_view_soft_delete_log(request.user):
        raise Http404("Stránka neexistuje.")

    state = parse_soft_delete_log_filter_request(request)
    qs = apply_soft_delete_log_filters(soft_delete_log_queryset(), state)

    per_page_raw = (request.GET.get("per_page") or "50").strip()
    try:
        per_page = int(per_page_raw)
    except ValueError:
        per_page = 50
    if per_page not in (25, 50, 100, 200):
        per_page = 50

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "waste_docs/ride_soft_delete/log_list.html",
        {
            "page_obj": page_obj,
            "items": page_obj,
            "per_page": per_page,
            "per_page_choices": (25, 50, 100, 200),
            "date_from": state.date_from,
            "date_to": state.date_to,
            "date_from_iso": state.date_from.isoformat() if state.date_from else "",
            "date_to_iso": state.date_to.isoformat() if state.date_to else "",
            "search_q": state.search_q,
        },
    )
