from __future__ import annotations

from django.db.models import Count
from django.http import HttpRequest

from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_KONTROLOR, ROLE_ZADAVATEL
from users.services.access import can_manage_dashboard_notes, can_see_all_waste_docs
from users.services.sberny_dvur import can_create_svoz_request, can_link_pruvodka_from_svoz_task
from catalogs.models import DriverProfile
from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_dispatch import customer_requests_visible_for_dispatch
from waste_docs.services.svoz_dispatch.plan_coverage import plan_coverage_has_any_gap
from waste_docs.services.svoz_dispatch import svoz_dispatch_soft_warnings
from waste_docs.services.svoz_dispatch.collection_yard_day_bundle import (
    get_collection_yard_day_bundle,
)
from waste_docs.services.yard_hazard_request.dashboard import open_hazard_requests_for_dashboard
from waste_docs.services.svoz_dispatch.dash_modal_yard_assignments import yard_driver_assignment_cards_for_date
from day_reminders.services.yard_dispatch_notes import yard_dispatch_notes_attention_for_date
from waste_docs.svoz_task_queries import svoz_tasks_open_for_date


def build_dashboard_dispatch_context(request: HttpRequest, selected_date, role: str) -> dict:
    user = request.user
    svoz_open_tasks = svoz_tasks_open_for_date(user, selected_date)
    customer_requests_visible_for_dispatch_list = []
    customer_requests_dispatcher_pending = []
    if user.is_superuser or role in {ROLE_DISPECER, ROLE_ADMIN}:
        customer_requests_visible_for_dispatch_list = list(
            customer_requests_visible_for_dispatch(user, selected_date)
        )
        customer_requests_dispatcher_pending = list(
            CustomerRequest.objects.filter(status=CustomerRequest.Status.DISPATCHER_REVIEW)
            .select_related("name", "activity", "created_by")
            .order_by("target_date", "created_at")[:20]
        )
    can_open_svoz_task_pruvodka = can_link_pruvodka_from_svoz_task(user)
    svoz_quick_edit_allowed = can_create_svoz_request(user) or can_see_all_waste_docs(user)
    svoz_quick_edit_drivers = []
    if svoz_quick_edit_allowed:
        svoz_quick_edit_drivers = list(
            DriverProfile.objects.order_by("last_name", "first_name", "personal_number")[:400]
        )
    dispatch_plan_needs_attention = False
    if can_see_all_waste_docs(user):
        yard_ids = list(get_collection_yard_day_bundle(selected_date).yard_ids)
        dispatch_plan_needs_attention = plan_coverage_has_any_gap(selected_date, yard_ids)

    yard_dispatch_notes_attention = False
    yard_dispatch_notes_count = 0
    if can_see_all_waste_docs(user):
        yard_dispatch_notes_attention, yard_dispatch_notes_count = (
            yard_dispatch_notes_attention_for_date(selected_date)
        )
    error_log_dash = {
        "yard_submit_error_unread_count": 0,
        "yard_submit_error_has_any": False,
        "yard_submit_error_groups": [],
    }
    if can_see_all_waste_docs(user):
        from waste_docs.services.svoz_matrix_submit_error_log import dispatcher_error_log_badge

        error_log_dash = dispatcher_error_log_badge()
    return {
        "svoz_open_tasks": svoz_open_tasks,
        "yard_dispatch_notes_attention": yard_dispatch_notes_attention,
        "yard_dispatch_notes_count": yard_dispatch_notes_count,
        "customer_requests_visible_for_dispatch": customer_requests_visible_for_dispatch_list,
        "customer_requests_dispatcher_pending": customer_requests_dispatcher_pending,
        "can_open_svoz_task_pruvodka": can_open_svoz_task_pruvodka,
        "svoz_quick_edit_allowed": svoz_quick_edit_allowed,
        "svoz_quick_edit_drivers": svoz_quick_edit_drivers,
        "svoz_dispatch_warnings": svoz_dispatch_soft_warnings(user, selected_date),
        "dispatch_plan_needs_attention": dispatch_plan_needs_attention,
        "yard_hazard_open_requests": open_hazard_requests_for_dashboard(user, selected_date),
        "can_manage_dashboard_notes": can_manage_dashboard_notes(user),
        "dash_svoz_yard_assignment_cards": yard_driver_assignment_cards_for_date(selected_date),
        **error_log_dash,
    }


def build_customer_request_counts(request: HttpRequest, role: str) -> dict:
    user = request.user
    is_super = user.is_superuser

    invoice_pending = 0
    invoice_overdue = 0
    if is_super or role in {ROLE_KONTROLOR, ROLE_ADMIN}:
        by_status = {
            row["status"]: row["c"]
            for row in (
                CustomerRequest.objects.filter(
                    requires_advance_invoice=True,
                    status__in=[
                        CustomerRequest.Status.SUBMITTED,
                        CustomerRequest.Status.INVOICE_OVERDUE,
                    ],
                )
                .values("status")
                .annotate(c=Count("id"))
            )
        }
        invoice_pending = int(by_status.get(CustomerRequest.Status.SUBMITTED, 0) or 0)
        invoice_overdue = int(by_status.get(CustomerRequest.Status.INVOICE_OVERDUE, 0) or 0)

    dispatcher_pending = 0
    if is_super or role in {ROLE_DISPECER, ROLE_ADMIN}:
        dispatcher_pending = CustomerRequest.objects.filter(
            status=CustomerRequest.Status.DISPATCHER_REVIEW
        ).count()

    submitter_back = 0
    if is_super or role in {ROLE_ZADAVATEL, ROLE_ADMIN}:
        submitter_back = CustomerRequest.objects.filter(
            created_by=user,
            status__in=[
                CustomerRequest.Status.RETURNED_FOR_FIX,
                CustomerRequest.Status.REQUIRES_RESCHEDULE,
                CustomerRequest.Status.INVOICE_REJECTED,
                CustomerRequest.Status.INVOICE_OVERDUE,
            ],
        ).count()

    return {
        "invoice_pending": invoice_pending,
        "invoice_overdue": invoice_overdue,
        "dispatcher_pending": dispatcher_pending,
        "submitter_back": submitter_back,
    }
