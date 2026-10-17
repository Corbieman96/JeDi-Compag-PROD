from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from core.services.list_pagination import paginate_queryset
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from waste_docs.services.customer_request_date_closure import is_target_date_closed
from waste_docs.services.customer_request_list_filters import (
    apply_customer_request_list_filters,
    apply_customer_request_list_ordering,
    parse_customer_request_list_filters,
)
from waste_docs.services.customer_request_fix.permissions import can_fix_customer_request
from waste_docs.services.customer_request_status_help import customer_request_status_help_rows
from waste_docs.services.customer_request_status import sync_page_items
from waste_docs.services.customer_request_status.list_reschedule_signal import (
    ride_reschedule_labels_for_page,
)

from .common import can_invoice_approve, role


@login_required
def customer_request_list(request):
    r = role(request.user)
    state = parse_customer_request_list_filters(request)

    qs = CustomerRequest.objects.select_related(
        "name",
        "activity",
        "vehicle_kind",
        "waste_type",
        "suffix",
        "created_by",
        "dispatcher_review_by",
        "invoice_confirmed_by",
    )
    if not request.user.is_superuser and r == ROLE_ZADAVATEL:
        qs = qs.filter(created_by=request.user)
    qs = apply_customer_request_list_ordering(apply_customer_request_list_filters(qs, state))

    pagination = paginate_queryset(qs, request)
    sync_page_items(pagination["page_obj"])
    page_items = list(pagination["page_obj"])
    fixable_ids = {item.pk for item in page_items if can_fix_customer_request(request.user, item)}
    fix_edit_urls = {
        pk: reverse("waste_docs:customer_request_form_edit", args=[pk]) for pk in fixable_ids
    }
    reschedule_labels = ride_reschedule_labels_for_page(page_items)
    page_rows = [
        {
            "item": item,
            "fix_edit_url": fix_edit_urls.get(item.pk),
            "reschedule_info": reschedule_labels.get(item.pk),
        }
        for item in page_items
    ]
    today = timezone.localdate()
    customer_request_today_closed = (
        r == ROLE_ZADAVATEL
        and not request.user.is_superuser
        and is_target_date_closed(today)
    )
    return render(
        request,
        "waste_docs/customer_request_list.html",
        {
            "items": pagination["page_obj"],
            "page_rows": page_rows,
            "page_obj": pagination["page_obj"],
            "per_page": pagination["per_page"],
            "per_page_choices": pagination["per_page_choices"],
            "elided_pages": pagination["elided_pages"],
            "pagination_preserve_query": pagination["pagination_preserve_query"],
            "status_filter": state.status_filter,
            "search_q": state.search_q,
            "status_choices": CustomerRequest.Status.choices,
            "status_help_rows": customer_request_status_help_rows(),
            "customer_request_today_closed": customer_request_today_closed,
        },
    )


@login_required
def customer_request_invoice_queue(request):
    if not can_invoice_approve(request.user):
        messages.error(request, "Nemáte oprávnění schvalovat zálohy.")
        return redirect("core:dashboard")

    today = timezone.localdate()
    q = (request.GET.get("q") or "").strip()
    base_qs = CustomerRequest.objects.select_related("name", "created_by", "activity").filter(
        requires_advance_invoice=True,
        status__in=[CustomerRequest.Status.SUBMITTED, CustomerRequest.Status.INVOICE_OVERDUE],
    )
    if q:
        base_qs = base_qs.filter(
            Q(name__value__icontains=q)
            | Q(created_by__username__icontains=q)
            | Q(created_by__first_name__icontains=q)
            | Q(created_by__last_name__icontains=q)
            | Q(pk__icontains=q)
        )

    rows_today = base_qs.filter(invoice_due_date=today).order_by("invoice_due_date", "created_at")
    # NULL splatnost = k řešení (jinak badge vs prázdná fronta).
    rows_overdue = base_qs.filter(
        Q(status=CustomerRequest.Status.INVOICE_OVERDUE)
        | Q(invoice_due_date__lt=today)
        | Q(invoice_due_date__isnull=True, status=CustomerRequest.Status.SUBMITTED)
    ).order_by("invoice_due_date", "created_at")
    rows_future = base_qs.filter(invoice_due_date__gt=today, status=CustomerRequest.Status.SUBMITTED).order_by(
        "invoice_due_date", "created_at"
    )

    context = {
        "q": q,
        "today": today,
        "rows_today": rows_today[:200],
        "rows_overdue": rows_overdue[:200],
        "rows_future": rows_future[:200],
        "count_today": rows_today.count(),
        "count_overdue": rows_overdue.count(),
        "count_total": base_qs.count(),
    }
    return render(request, "waste_docs/customer_request_invoice_queue.html", context)
