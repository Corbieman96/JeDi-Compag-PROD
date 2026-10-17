from urllib.parse import urlencode
from datetime import timedelta

from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from users.services.waste_doc_permissions import can_archive_pruvodka, can_create_pruvodka, can_delete_all_pruvodky
from waste_docs.services.ride_soft_delete.permissions import can_view_soft_delete_log
from waste_docs.services.pruvodka_list_default_range import (
    default_range_days_from_settings,
    get_pruvodka_list_queryset_resolved,
)
from waste_docs.views.access import waste_docs_list_access_required


@waste_docs_list_access_required
def pruvodka_list(request):
    queryset, state, is_default_range, show_all = get_pruvodka_list_queryset_resolved(
        request, user=request.user
    )

    selected_date = state.selected_date
    date_from = state.date_from
    date_to = state.date_to
    awaiting = state.awaiting_follow_up
    blank_only = state.blank_only
    search_q = state.search_q

    default_range_days = default_range_days_from_settings()

    has_range_filter = (
        show_all is False
        and (
            is_default_range
            or bool((request.GET.get("date_from") or "").strip() or (request.GET.get("date_to") or "").strip())
        )
    )
    if date_to:
        request.session["waste_docs_last_date_to"] = date_to.isoformat()

    session_last_date_to = None
    session_last_date_to_raw = (request.session.get("waste_docs_last_date_to") or "").strip()
    if session_last_date_to_raw:
        try:
            session_last_date_to = timezone.datetime.strptime(session_last_date_to_raw, "%Y-%m-%d").date()
        except ValueError:
            session_last_date_to = None

    if has_range_filter:
        ui_date_from = date_from.isoformat() if date_from else ""
        ui_date_to = date_to.isoformat() if date_to else ""
    else:
        default_to = session_last_date_to or selected_date or timezone.localdate()
        default_from = default_to - timedelta(days=default_range_days)
        ui_date_from = default_from.isoformat()
        ui_date_to = default_to.isoformat()

    export_params = {}
    if selected_date:
        export_params["date"] = selected_date.isoformat()
    if date_from:
        export_params["date_from"] = date_from.isoformat()
    if date_to:
        export_params["date_to"] = date_to.isoformat()
    if awaiting:
        export_params["awaiting_follow_up"] = "1"
    if blank_only:
        export_params["blank_only"] = "1"
    if search_q:
        export_params["q"] = search_q
    export_query_string = urlencode(export_params)

    per_page_raw = (request.GET.get("per_page") or "50").strip()
    try:
        per_page = int(per_page_raw)
    except ValueError:
        per_page = 50
    if per_page not in (25, 50, 100, 200):
        per_page = 50

    paginator = Paginator(queryset, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    if awaiting:
        today = timezone.localdate()
        for item in page_obj.object_list:
            item.follow_up_days_on_site = max(0, (today - item.drive_date).days)

    elided_pages = []
    if paginator.num_pages > 1:
        for p in paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1):
            if isinstance(p, int):
                elided_pages.append({"ellipsis": False, "number": p})
            else:
                elided_pages.append({"ellipsis": True})

    return render(
        request,
        "waste_docs/list.html",
        {
            "page_obj": page_obj,
            "items": page_obj,
            "per_page": per_page,
            "per_page_choices": (25, 50, 100, 200),
            "elided_pages": elided_pages,
            "selected_date": selected_date,
            "selected_date_iso": selected_date.isoformat() if selected_date else "",
            "date_from": date_from,
            "date_to": date_to,
            "date_from_iso": date_from.isoformat() if date_from else "",
            "date_to_iso": date_to.isoformat() if date_to else "",
            "ui_date_from_iso": ui_date_from,
            "ui_date_to_iso": ui_date_to,
            "has_range_filter": has_range_filter,
            "awaiting_follow_up": awaiting,
            "blank_only": blank_only,
            "search_q": search_q,
            "export_query_string": export_query_string,
            "can_create_pruvodka": can_create_pruvodka(request.user),
            "can_archive_blank_pruvodka": can_archive_pruvodka(request.user),
            "can_delete_all_pruvodky": can_delete_all_pruvodky(request.user),
            "can_view_soft_delete_log": can_view_soft_delete_log(request.user),
        },
    )
