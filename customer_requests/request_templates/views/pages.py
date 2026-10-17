from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from catalogs.catalog_nav_registry import SLUG_CUSTOMER_REQUEST_TEMPLATES
from customer_requests.request_templates.forms import CustomerRequestTemplateForm
from customer_requests.request_templates.services.create_from_payload import (
    create_customer_request_template_from_payload,
)
from customer_requests.request_templates.services.serialization import customer_request_template_to_json
from customer_requests.request_templates.services.visibility import (
    customer_request_templates_visible_queryset,
)
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from waste_docs.views.customer_requests.common import can_submit

logger = logging.getLogger(__name__)


def customer_request_templates_access_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated
        and effective_show_catalog_index_row(u, SLUG_CUSTOMER_REQUEST_TEMPLATES)
    )(view)


@login_required
@customer_request_templates_access_required
def template_list(request):
    items = (
        customer_request_templates_visible_queryset(request.user)
        .select_related(
            "name",
            "waste_type",
            "suffix",
            "address",
            "activity",
            "vehicle_kind",
            "created_by",
        )
        .order_by("title", "-updated_at")
    )
    return render(
        request,
        "customer_request_templates/list.html",
        {"items": items},
    )


@login_required
@customer_request_templates_access_required
def template_create(request):
    form = CustomerRequestTemplateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.save()
        return redirect("customer_request_templates:list")
    return render(
        request,
        "customer_request_templates/form.html",
        {"form": form, "page_title": "Nová šablona požadavku"},
    )


@login_required
@customer_request_templates_access_required
def template_edit(request, pk: int):
    item = get_object_or_404(customer_request_templates_visible_queryset(request.user), pk=pk)
    form = CustomerRequestTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("customer_request_templates:list")
    return render(
        request,
        "customer_request_templates/form.html",
        {"form": form, "page_title": "Upravit šablonu požadavku", "item": item},
    )


@login_required
@customer_request_templates_access_required
def template_delete(request, pk: int):
    item = get_object_or_404(customer_request_templates_visible_queryset(request.user), pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("customer_request_templates:list")
    return render(
        request,
        "customer_request_templates/confirm_delete.html",
        {"item": item},
    )


@login_required
@require_GET
@customer_request_templates_access_required
def template_api_list(request):
    if not can_submit(request.user):
        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)
    rows = (
        customer_request_templates_visible_queryset(request.user)
        .select_related("name", "address", "waste_type", "suffix", "created_by")
        .order_by("title", "-updated_at")
    )
    return JsonResponse(
        {"ok": True, "data": [customer_request_template_to_json(row) for row in rows]}
    )


@login_required
@require_POST
@customer_request_templates_access_required
def template_api_save(request):
    if not can_submit(request.user):
        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)
    try:
        if request.content_type and "application/json" in request.content_type:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        else:
            payload = request.POST.dict()
        tpl = create_customer_request_template_from_payload(user=request.user, payload=payload)
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception("Uložení šablony požadavku selhalo.")
        return JsonResponse({"ok": False, "error": "Šablonu se nepodařilo uložit."}, status=400)
    return JsonResponse({"ok": True, "data": customer_request_template_to_json(tpl)})
