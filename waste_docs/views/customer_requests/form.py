"""View pro opravu a smazání zákaznického požadavku."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalogs.services.waste_type_labels import waste_type_combo_metadata
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from waste_docs.follow_up_options import allowed_follow_up_activity_ids
from waste_docs.forms import CustomerRequestForm
from waste_docs.services.customer_request_form.actions import (
    cancel_fix,
    hard_delete_fix,
    resubmit_fix,
    save_fix,
)
from waste_docs.services.customer_request_form.cancel_reason import normalize_cancel_reason
from waste_docs.services.customer_request_form.client_config import customer_request_form_client_config
from waste_docs.services.customer_request_form.permissions import (
    can_delete_customer_request,
    can_fix_customer_request,
)
from waste_docs.services.customer_request_form.subject_snapshot import (
    subject_snapshot_for_customer_request_form,
)
from waste_docs.services.customer_request_submitter_feedback import build_submitter_fix_feedback

from .common import role


def _form_render_context(
    request,
    *,
    form: CustomerRequestForm,
    item: CustomerRequest | None,
    page_title: str,
    is_edit: bool,
) -> dict:
    can_edit_name_subject_pairs = effective_show_catalog_index_row(request.user, "name")
    initial_subject_snapshot = None
    if is_edit and item is not None and item.name_id:
        initial_subject_snapshot = subject_snapshot_for_customer_request_form(name_id=item.name_id)

    activity_follow_map = {
        str(a.pk): [
            {"id": follow.pk, "name": follow.name}
            for follow in form.fields["follow_up_activity"].queryset.filter(
                pk__in=allowed_follow_up_activity_ids(a)
            )
        ]
        for a in form.fields["activity"].queryset.prefetch_related("follow_up_activities")
    }

    return {
        "form": form,
        "item": item,
        "is_edit": is_edit,
        "page_title": page_title,
        "waste_type_combo_meta": waste_type_combo_metadata(),
        "can_edit_name_subject_pairs": can_edit_name_subject_pairs,
        "customer_request_form_config": customer_request_form_client_config(
            can_edit_name_subject_pairs=can_edit_name_subject_pairs,
            submit_user=request.user,
            initial_subject_snapshot=initial_subject_snapshot,
        ),
        "activity_follow_map": activity_follow_map,
        "fix_feedback": build_submitter_fix_feedback(item) if item is not None else None,
    }


def _attach_fix_delete_context(ctx: dict, *, user, item: CustomerRequest) -> dict:
    can_delete = can_delete_customer_request(user, item)
    ctx["can_delete_fix"] = can_delete
    ctx["fix_delete_url"] = (
        reverse("waste_docs:customer_request_form_delete", args=[item.pk]) if can_delete else ""
    )
    return ctx


@login_required
def customer_request_form_edit(request, pk: int):
    item = get_object_or_404(
        CustomerRequest.objects.select_related("name", "address", "waste_type"),
        pk=pk,
    )
    r = role(request.user)
    if (
        not request.user.is_superuser
        and r == ROLE_ZADAVATEL
        and item.created_by_id != request.user.pk
    ):
        messages.error(request, "Tento požadavek nepatří k vašemu účtu.")
        return redirect("waste_docs:customer_request_list")

    if not can_fix_customer_request(request.user, item):
        messages.error(request, "Požadavek nelze v aktuálním stavu opravit.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    form = CustomerRequestForm(
        request.POST or None,
        request.FILES or None,
        instance=item,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "save").strip()
        if action == "cancel":
            try:
                reason = normalize_cancel_reason(
                    request.POST.get("cancel_reason") or request.POST.get("note")
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                ctx = _form_render_context(
                    request,
                    form=form,
                    item=item,
                    page_title=f"Oprava požadavku #{item.pk}",
                    is_edit=True,
                )
                _attach_fix_delete_context(ctx, user=request.user, item=item)
                ctx["cancel_reason"] = (request.POST.get("cancel_reason") or "").strip()
                return render(request, "waste_docs/customer_request_form.html", ctx)

            with transaction.atomic():
                cancel_fix(item=item, actor=request.user, note=reason)
            messages.success(request, "Požadavek byl zrušen.")
            return redirect("waste_docs:customer_request_list")

        if form.is_valid():
            with transaction.atomic():
                if action == "resubmit":
                    resubmit_fix(form=form, item=item, actor=request.user)
                    messages.success(
                        request,
                        "Požadavek byl opraven a odeslán k dalšímu schválení.",
                    )
                else:
                    save_fix(form=form, item=item, actor=request.user)
                    messages.success(request, "Oprava požadavku byla uložena.")
            return redirect("waste_docs:customer_request_detail", pk=item.pk)

    ctx = _form_render_context(
        request,
        form=form,
        item=item,
        page_title=f"Oprava požadavku #{item.pk}",
        is_edit=True,
    )
    _attach_fix_delete_context(ctx, user=request.user, item=item)
    return render(request, "waste_docs/customer_request_form.html", ctx)


@login_required
@require_POST
def customer_request_form_delete(request, pk: int):
    item = get_object_or_404(CustomerRequest, pk=pk)
    r = role(request.user)
    if (
        not request.user.is_superuser
        and r == ROLE_ZADAVATEL
        and item.created_by_id != request.user.pk
    ):
        messages.error(request, "Tento požadavek nepatří k vašemu účtu.")
        return redirect("waste_docs:customer_request_list")

    if not can_delete_customer_request(request.user, item):
        messages.error(request, "Požadavek nelze smazat.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    try:
        with transaction.atomic():
            hard_delete_fix(item=item)
    except ProtectedError:
        messages.error(
            request,
            "Požadavek nelze smazat, protože má navazující požadavek. Nejprve upravte nebo smažte navazující záznam.",
        )
        return redirect("waste_docs:customer_request_detail", pk=pk)
    messages.success(request, "Požadavek byl trvale smazán.")
    return redirect("waste_docs:customer_request_list")


# Alias kvůli dřívější Windows kolizi form/fix.
customer_request_fix_edit = customer_request_form_edit
customer_request_fix_delete = customer_request_form_delete
