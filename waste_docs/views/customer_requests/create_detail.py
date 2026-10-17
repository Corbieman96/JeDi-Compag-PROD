from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.db import transaction

from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse



from catalogs.services.waste_type_labels import waste_type_combo_metadata

from users.constants import ROLE_ZADAVATEL
from users.services.catalog_row_visibility import effective_show_catalog_index_row

from waste_docs.follow_up_options import allowed_follow_up_activity_ids

from waste_docs.forms import CustomerRequestForm

from customer_requests.models import CustomerRequest

from waste_docs.services.customer_request_audit import log_customer_request_action

from waste_docs.services.customer_request_fix.actions import status_after_resubmit
from waste_docs.services.customer_request_fix.persist import apply_form_to_request
from waste_docs.services.customer_request_fix.permissions import (
    can_delete_customer_request,
    can_fix_customer_request,
)
from waste_docs.services.customer_request_follow_up_spawn import spawn_follow_up_customer_request
from waste_docs.services.customer_request_form.client_config import customer_request_form_client_config

from waste_docs.services.customer_request_map_coords import resolve_customer_request_map_coords

from waste_docs.services.customer_request_status import sync_customer_request_status

from waste_docs.services.customer_request_status.align_ride_date import latest_ride_rescheduled_banner

from .common import (

    AUDIT_ACTION_LABELS,

    can_dispatcher_review,

    can_invoice_approve,

    can_plan_rides,

    can_submit,

    role,

)





@login_required

def customer_request_create(request):

    if not can_submit(request.user):

        messages.error(request, "Nemáte oprávnění založit požadavek.")

        return redirect("waste_docs:customer_request_list")



    form = CustomerRequestForm(request.POST or None, request.FILES or None, submit_user=request.user)

    if request.method == "POST" and form.is_valid():

        with transaction.atomic():

            req = form.save(commit=False)

            req.created_by = request.user

            req.status = status_after_resubmit(req)

            apply_form_to_request(form=form, item=req)

            child = None
            if req.has_follow_up and req.follow_up_activity_id and req.follow_up_target_date:
                child = spawn_follow_up_customer_request(parent=req, actor=request.user)
            else:
                log_customer_request_action(req, request.user, "create", "Požadavek založen.")

        if child:
            messages.success(
                request,
                f"Založeny požadavky #{req.pk} (základní) a #{child.pk} (navazující).",
            )
        else:
            messages.success(request, "Požadavek byl založen.")
        for note in form.operating_date_shift_notes:
            messages.info(request, note)

        return redirect("waste_docs:customer_request_detail", pk=req.pk)



    can_edit_name_subject_pairs = effective_show_catalog_index_row(request.user, "name")

    return render(

        request,

        "waste_docs/customer_request_form.html",

        {

            "form": form,

            "item": None,

            "page_title": "Nový požadavek",

            "waste_type_combo_meta": waste_type_combo_metadata(),

            "can_edit_name_subject_pairs": can_edit_name_subject_pairs,

            "customer_request_form_config": customer_request_form_client_config(
                can_edit_name_subject_pairs=can_edit_name_subject_pairs,
                submit_user=request.user,
            ),

            "activity_follow_map": {

                str(a.pk): [

                    {"id": follow.pk, "name": follow.name}

                    for follow in form.fields["follow_up_activity"].queryset.filter(

                        pk__in=allowed_follow_up_activity_ids(a)

                    )

                ]

                for a in form.fields["activity"].queryset.prefetch_related("follow_up_activities")

            },

        },

    )





@login_required

def customer_request_detail(request, pk: int):

    item = get_object_or_404(

        CustomerRequest.objects.select_related(

            "name",

            "activity",

            "vehicle_kind",

            "waste_type",

            "suffix",

            "address",

            "created_by",

            "dispatcher_review_by",

            "invoice_confirmed_by",

            "follow_up_activity",

            "follow_up_parent_request",

        ).prefetch_related("attachments", "audit_logs__actor", "activity__vehicle_kinds", "follow_up_child_requests"),

        pk=pk,

    )

    r = role(request.user)

    if not request.user.is_superuser and r == ROLE_ZADAVATEL and item.created_by_id != request.user.pk:

        messages.error(request, "Tento požadavek nepatří k vašemu účtu.")

        return redirect("waste_docs:customer_request_list")

    sync_customer_request_status(item, actor=request.user)
    item.refresh_from_db()

    map_lat, map_lng = resolve_customer_request_map_coords(item)

    audit_rows = []

    for log in item.audit_logs.all():

        audit_rows.append(

            {

                "created_at": log.created_at,

                "actor": log.actor,

                "note": log.note,

                "action_label": AUDIT_ACTION_LABELS.get(log.action, log.action),

            }

        )

    can_fix = can_fix_customer_request(request.user, item)
    fix_edit_url = (
        reverse("waste_docs:customer_request_form_edit", args=[item.pk]) if can_fix else ""
    )

    return render(

        request,

        "waste_docs/customer_request_detail.html",

        {

            "item": item,

            "request_map_lat": map_lat,

            "request_map_lng": map_lng,

            "audit_rows": audit_rows,

            "ride_reschedule_info": latest_ride_rescheduled_banner(item),

            "can_invoice_approve": can_invoice_approve(request.user),

            "can_dispatcher_review": can_dispatcher_review(request.user),

            "can_submitter_edit": can_submit(request.user) and item.created_by_id == request.user.pk,

            "can_fix_request": can_fix,

            "fix_edit_url": fix_edit_url,

            "can_delete_request": can_delete_customer_request(request.user, item),

            "can_plan_rides": can_plan_rides(request.user),

            "can_show_day_kind_counts_modal": can_dispatcher_review(request.user),

        },

    )

