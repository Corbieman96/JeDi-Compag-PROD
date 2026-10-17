from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from day_reminders.services import build_dashboard_context
from users.services.access import app_role
from users.services.waste_doc_permissions import can_create_pruvodka, can_create_pruvodka_dashboard, can_purge_dashboard_day_files, can_archive_pruvodka

from core.services.dashboard_customer_requests import (
    build_customer_request_counts,
    build_dashboard_dispatch_context,
)
from waste_docs.customer_request_kind_closure.services.dashboard import (
    dashboard_kind_closure_context,
)
from waste_docs.services.customer_request_date_closure import dashboard_closure_context
from core.services.dashboard_drivers import build_dashboard_drivers_context
from core.services.dashboard_print_links import (
    annotate_ride_groups_print_pks,
    dashboard_header_print_url,
    filter_pks_for_email_group,
    parse_selected_ride_pk,
)
from core.services.dashboard_rides import build_dashboard_rides_section

logger = logging.getLogger(__name__)


def _dispatch_fallback_context() -> dict:
    return {
        "svoz_open_tasks": [],
        "yard_dispatch_notes_attention": False,
        "yard_dispatch_notes_count": 0,
        "customer_requests_visible_for_dispatch": [],
        "customer_requests_dispatcher_pending": [],
        "can_open_svoz_task_pruvodka": False,
        "svoz_quick_edit_allowed": False,
        "svoz_quick_edit_drivers": [],
        "svoz_dispatch_warnings": [],
        "dispatch_plan_needs_attention": False,
        "yard_hazard_open_requests": [],
        "can_manage_dashboard_notes": False,
        "dash_svoz_yard_assignment_cards": [],
        "yard_submit_error_unread_count": 0,
        "yard_submit_error_has_any": False,
        "yard_submit_error_groups": [],
    }


def _customer_request_debug_snapshot(selected_date) -> list[dict]:
    try:
        from customer_requests.models import CustomerRequest

        rows = (
            CustomerRequest.objects.filter(target_date=selected_date)
            .values(
                "pk",
                "status",
                "target_date",
                "has_follow_up",
                "follow_up_activity_id",
                "follow_up_parent_request_id",
                "planned_pruvodka_id",
            )
            .order_by("pk")[:20]
        )
        return [dict(row) for row in rows]
    except Exception:
        return []


def dashboard_selected_date(request: HttpRequest):
    date_raw = (request.GET.get("date") or "").strip()
    today = timezone.localdate()
    try:
        selected_date = datetime.strptime(date_raw, "%Y-%m-%d").date() if date_raw else today
    except ValueError:
        selected_date = today
    iso = selected_date.isoformat()
    if request.session.get("dashboard_selected_date") != iso:
        request.session["dashboard_selected_date"] = iso
    return selected_date, today


def build_dashboard_page_context(request: HttpRequest) -> dict:
    """Úvodní přehled: řidiči, vozidla, dostupnost, průvodky (jízdy) podle dne, poznámky."""
    selected_date, today = dashboard_selected_date(request)
    ride_group_key = (request.GET.get("ride_group") or "").strip()
    rides_ctx, rides_day_qs = build_dashboard_rides_section(request.user, selected_date, ride_group_key)
    selected_ride_group = rides_ctx.get("selected_ride_group")
    ride_group_explicit = bool(selected_ride_group)
    selected_ride_pk = parse_selected_ride_pk((request.GET.get("ride_pk") or "").strip(), selected_ride_group)
    annotate_ride_groups_print_pks(rides_ctx.get("ride_groups") or [], selected_ride_pk)
    selected_ride_group_email_pks = ""
    if selected_ride_group:
        selected_ride_group_email_pks = ",".join(
            str(pk) for pk in filter_pks_for_email_group(selected_ride_group, selected_ride_pk)
        )
    drivers_ctx = build_dashboard_drivers_context(selected_date, rides_day_qs)
    role = app_role(request.user)
    dashboard_debug_messages: list[str] = []
    try:
        dispatch_ctx = build_dashboard_dispatch_context(request, selected_date, role)
    except Exception:
        logger.exception(
            "Dashboard dispatch section failed for date=%s user_id=%s role=%s",
            selected_date.isoformat(),
            getattr(request.user, "pk", None),
            role,
        )
        logger.error(
            "Dashboard dispatch debug snapshot for date=%s: %s",
            selected_date.isoformat(),
            _customer_request_debug_snapshot(selected_date),
        )
        dispatch_ctx = _dispatch_fallback_context()
        dashboard_debug_messages.append(
            "Chyba načtení části Požadavky/dispatch. Dashboard běží v nouzovém režimu; detail je v server logu."
        )

    context = {
        "selected_date": selected_date,
        "selected_date_iso": selected_date.isoformat(),
        "prev_date": selected_date - timedelta(days=1),
        "next_date": selected_date + timedelta(days=1),
        "today": today,
        "can_create_pruvodka": can_create_pruvodka(request.user),
        "can_create_pruvodka_dashboard": can_create_pruvodka_dashboard(request.user),
        "can_archive_blank_pruvodka": can_archive_pruvodka(request.user),
        "can_purge_dashboard_day_files": can_purge_dashboard_day_files(request.user),
        "selected_ride_pk": selected_ride_pk,
        "selected_ride_group_email_pks": selected_ride_group_email_pks,
        "ride_group_explicit": ride_group_explicit,
        "dashboard_header_print_url": dashboard_header_print_url(
            selected_date,
            selected_ride_group,
            selected_ride_pk,
            ride_group_explicit=ride_group_explicit,
        ),
        "dashboard_clear_ride_selection_url": (
            f"{reverse('core:dashboard')}?date={selected_date.isoformat()}"
        ),
        "dashboard_debug_messages": dashboard_debug_messages,
        **rides_ctx,
        **drivers_ctx,
        **dispatch_ctx,
    }
    context["customer_request_counts"] = build_customer_request_counts(request, role)
    context["customer_request_closure"] = dashboard_closure_context(
        selected_date,
        user=request.user,
        now=timezone.localtime(),
    )
    context["customer_request_kind_closure"] = dashboard_kind_closure_context(
        selected_date,
        user=request.user,
    )
    context.update(build_dashboard_context(selected_date))
    from waste_docs.services.ride_reassign_driver.context import build_ride_reassign_driver_context

    context.update(build_ride_reassign_driver_context(selected_ride_group, request.user))
    return context
