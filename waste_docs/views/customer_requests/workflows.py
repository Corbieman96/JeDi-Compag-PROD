from datetime import date



from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.db import transaction

from django.http import JsonResponse

from django.shortcuts import get_object_or_404, redirect

from django.utils import timezone

from django.views.decorators.http import require_POST



from catalogs.models import NameCatalog

from customer_requests.models import CustomerRequest

from waste_docs.services.customer_request_audit import log_customer_request_action
from waste_docs.services.customer_request_follow_up import follow_up_target_date_error
from waste_docs.customer_request_kind_closure.services.checks import vehicle_kind_closure_error
from waste_docs.services.customer_request_date_closure import target_date_closure_error
from waste_docs.services.customer_request_vehicle_kind import effective_vehicle_kind_id
from waste_docs.services.customer_request_form.cancel_reason import normalize_cancel_reason
from waste_docs.services.customer_request_recurrence import (
    ensure_recurrence_occurrences,
    format_recurrence_label,
)

from .common import (

    can_dispatcher_review,

    can_invoice_approve,

    can_plan_rides,

    can_submit,

)





@login_required

@require_POST

def customer_request_submitter_update(request, pk: int):

    item = get_object_or_404(CustomerRequest, pk=pk)

    if not can_submit(request.user) or item.created_by_id != request.user.pk:

        messages.error(request, "Nemáte oprávnění upravit požadavek.")

        return redirect("waste_docs:customer_request_detail", pk=pk)

    if item.status not in {

        CustomerRequest.Status.RETURNED_FOR_FIX,

        CustomerRequest.Status.REQUIRES_RESCHEDULE,

        CustomerRequest.Status.INVOICE_OVERDUE,

        CustomerRequest.Status.INVOICE_REJECTED,

    }:

        messages.warning(request, "Požadavek nelze v aktuálním stavu upravit tímto postupem.")

        return redirect("waste_docs:customer_request_detail", pk=pk)



    action = (request.POST.get("action") or "").strip()

    note = (request.POST.get("note") or "").strip()

    date_raw = (request.POST.get("target_date") or "").strip()

    follow_date_raw = (request.POST.get("follow_up_target_date") or "").strip()

    invoice_due_raw = (request.POST.get("invoice_due_date") or "").strip()

    if action == "resubmit":

        if date_raw:

            try:

                new_target_date = date.fromisoformat(date_raw)

            except ValueError:

                messages.error(request, "Neplatné datum přeplánování.")

                return redirect("waste_docs:customer_request_detail", pk=pk)

            if new_target_date != item.target_date:
                err = target_date_closure_error(new_target_date, user=request.user)
                if err:
                    messages.error(request, err)
                    return redirect("waste_docs:customer_request_detail", pk=pk)
                kind_err = vehicle_kind_closure_error(
                    new_target_date,
                    effective_vehicle_kind_id(item),
                    user=request.user,
                )
                if kind_err:
                    messages.error(request, kind_err)
                    return redirect("waste_docs:customer_request_detail", pk=pk)
            item.target_date = new_target_date

        if follow_date_raw:

            try:

                follow_date = date.fromisoformat(follow_date_raw)

            except ValueError:

                messages.error(request, "Neplatné datum navazující činnosti.")

                return redirect("waste_docs:customer_request_detail", pk=pk)

            err = follow_up_target_date_error(item.target_date, follow_date)

            if err:

                messages.error(request, err)

                return redirect("waste_docs:customer_request_detail", pk=pk)

            item.follow_up_target_date = follow_date

        if invoice_due_raw:

            try:

                item.invoice_due_date = date.fromisoformat(invoice_due_raw)

            except ValueError:

                messages.error(request, "Neplatné datum splatnosti zálohy.")

                return redirect("waste_docs:customer_request_detail", pk=pk)

        item.status = (

            CustomerRequest.Status.SUBMITTED

            if item.requires_advance_invoice

            else CustomerRequest.Status.DISPATCHER_REVIEW

        )

        item.save(update_fields=["status", "target_date", "follow_up_target_date", "invoice_due_date", "updated_at"])

        log_customer_request_action(item, request.user, "resubmit", note or "Zadavatel poslal znovu.")

        messages.success(request, "Požadavek byl odeslán k dalšímu schválení.")

    elif action == "cancel":

        try:

            reason = normalize_cancel_reason(note)

        except ValueError as exc:

            messages.error(request, str(exc))

            return redirect("waste_docs:customer_request_detail", pk=pk)

        item.status = CustomerRequest.Status.CANCELLED

        item.save(update_fields=["status", "updated_at"])

        log_customer_request_action(item, request.user, "cancel", reason)

        messages.success(request, "Požadavek byl zrušen.")

    else:

        messages.error(request, "Neplatná akce.")

    return redirect("waste_docs:customer_request_detail", pk=pk)





@login_required

@require_POST

def customer_request_invoice_review(request, pk: int):

    if not can_invoice_approve(request.user):

        messages.error(request, "Nemáte oprávnění schválit zálohu.")

        return redirect("waste_docs:customer_request_detail", pk=pk)

    item = get_object_or_404(CustomerRequest, pk=pk)

    if item.status not in {CustomerRequest.Status.SUBMITTED, CustomerRequest.Status.INVOICE_OVERDUE}:

        messages.warning(request, "Požadavek není ve stavu čekání na zálohu.")

        return redirect("waste_docs:customer_request_detail", pk=pk)



    action = (request.POST.get("action") or "").strip()

    note = (request.POST.get("note") or "").strip()

    next_url = (request.POST.get("next") or "").strip()

    with transaction.atomic():

        if action == "approve":

            item.mark_invoice_approved(request.user, note)

            log_customer_request_action(item, request.user, "invoice_approved", note)

            msg = "Záloha byla schválena."

        elif action == "unpaid_overdue":

            item.status = CustomerRequest.Status.INVOICE_OVERDUE

            item.invoice_confirmed_by = request.user

            item.invoice_confirmed_at = timezone.now()

            item.invoice_note = note or "Nezaplaceno ve splatnosti."

            log_customer_request_action(item, request.user, "invoice_unpaid_overdue", item.invoice_note)

            msg = "Požadavek je označen jako nezaplacený po splatnosti."

        elif action == "reject":

            item.status = CustomerRequest.Status.INVOICE_REJECTED

            item.invoice_confirmed_by = request.user

            item.invoice_confirmed_at = timezone.now()

            item.invoice_note = note

            log_customer_request_action(item, request.user, "invoice_rejected", note)

            msg = "Záloha byla zamítnuta."

        else:

            messages.error(request, "Neplatná akce.")

            return redirect("waste_docs:customer_request_detail", pk=pk)

        item.save()

    messages.success(request, msg)

    if next_url:

        return redirect(next_url)

    return redirect("waste_docs:customer_request_detail", pk=pk)





@login_required

@require_POST

def customer_request_dispatcher_review(request, pk: int):

    if not can_dispatcher_review(request.user):

        messages.error(request, "Nemáte oprávnění dispečerského schválení.")

        return redirect("waste_docs:customer_request_detail", pk=pk)

    item = get_object_or_404(CustomerRequest, pk=pk)

    if item.status != CustomerRequest.Status.DISPATCHER_REVIEW:

        messages.warning(request, "Požadavek není ve frontě dispečera.")

        return redirect("waste_docs:customer_request_detail", pk=pk)



    action = (request.POST.get("action") or "").strip()

    note = (request.POST.get("note") or "").strip()

    with transaction.atomic():

        if action == "approve":

            item.mark_dispatcher_approved(request.user, note)

            log_customer_request_action(item, request.user, "dispatcher_approved", note)

            created = ensure_recurrence_occurrences(item, request.user)

            if created:

                label = format_recurrence_label(item.recurrence_weekdays, item.recurrence_until)

                msg = (
                    f"Požadavek je schválen a viditelný pro dispečera. "
                    f"Založeno {len(created)} dalších termínů ({label})."
                )

            else:

                msg = "Požadavek je schválen a viditelný pro dispečera."

        elif action == "return":

            item.dispatcher_review_by = request.user

            item.dispatcher_reviewed_at = timezone.now()

            item.dispatcher_note = note

            item.status = CustomerRequest.Status.RETURNED_FOR_FIX

            log_customer_request_action(item, request.user, "dispatcher_returned", note)

            msg = "Požadavek byl vrácen zadavateli k opravě."

        elif action == "reschedule":

            item.dispatcher_review_by = request.user

            item.dispatcher_reviewed_at = timezone.now()

            item.dispatcher_note = note

            item.status = CustomerRequest.Status.REQUIRES_RESCHEDULE

            log_customer_request_action(item, request.user, "dispatcher_requires_reschedule", note)

            msg = "Požadavek vyžaduje přeplánování."

        elif action == "cancel":

            try:

                note = normalize_cancel_reason(note)

            except ValueError as exc:

                messages.error(request, str(exc))

                return redirect("waste_docs:customer_request_detail", pk=pk)

            item.dispatcher_review_by = request.user

            item.dispatcher_reviewed_at = timezone.now()

            item.dispatcher_note = note

            item.status = CustomerRequest.Status.CANCELLED

            log_customer_request_action(item, request.user, "dispatcher_cancelled", note)

            msg = "Požadavek byl zrušen dispečerem."

        else:

            messages.error(request, "Neplatná akce.")

            return redirect("waste_docs:customer_request_detail", pk=pk)

        item.save()

    messages.success(request, msg)

    return redirect("waste_docs:customer_request_detail", pk=pk)




@login_required
@require_POST
def customer_request_expand_recurrence(request, pk: int):
    if not can_dispatcher_review(request.user):
        messages.error(request, "Nemáte oprávnění doplnit opakované termíny.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    item = get_object_or_404(CustomerRequest, pk=pk)
    if item.recurrence_parent_request_id:
        messages.warning(request, "Tento požadavek je už součástí opakované série.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    if item.status != CustomerRequest.Status.VISIBLE_FOR_DISPATCH:
        messages.warning(request, "Opakované termíny lze doplnit až po schválení požadavku.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    if not item.is_recurring:
        messages.warning(request, "Požadavek není označený jako pravidelný.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    with transaction.atomic():
        created = ensure_recurrence_occurrences(item, request.user)

    if created:
        label = format_recurrence_label(item.recurrence_weekdays, item.recurrence_until)
        messages.success(
            request,
            f"Založeno {len(created)} opakovaných termínů ({label}).",
        )
    else:
        messages.info(request, "Všechny termíny opakování už existují.")
    return redirect("waste_docs:customer_request_detail", pk=pk)


@login_required
@require_POST
def customer_request_set_follow_up_date(request, pk: int):
    if not (can_plan_rides(request.user) or can_dispatcher_review(request.user)):
        messages.error(request, "Nemáte oprávnění upravit datum navazující činnosti.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    item = get_object_or_404(CustomerRequest, pk=pk)

    if item.planned_pruvodka_id:
        messages.warning(request, "Požadavek už má založenou jízdu.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    if item.status not in {
        CustomerRequest.Status.DISPATCHER_REVIEW,
        CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
    }:
        messages.warning(request, "Požadavek nelze v aktuálním stavu upravit.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    if not item.has_follow_up:
        messages.warning(request, "Požadavek nemá navazující činnost.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    follow_date_raw = (request.POST.get("follow_up_target_date") or "").strip()
    if not follow_date_raw:
        messages.error(request, "Vyplňte datum navazující činnosti.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    try:
        follow_date = date.fromisoformat(follow_date_raw)
    except ValueError:
        messages.error(request, "Neplatné datum navazující činnosti.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    err = follow_up_target_date_error(item.target_date, follow_date)
    if err:
        messages.error(request, err)
        return redirect("waste_docs:customer_request_detail", pk=pk)

    item.follow_up_target_date = follow_date
    item.save(update_fields=["follow_up_target_date", "updated_at"])
    log_customer_request_action(
        item,
        request.user,
        "follow_up_date_set",
        follow_date.isoformat(),
    )
    messages.success(request, "Datum navazující činnosti bylo uloženo.")
    return redirect("waste_docs:customer_request_detail", pk=pk)


@login_required

@require_POST

def customer_request_create_name_ajax(request):

    if not can_submit(request.user):

        return JsonResponse({"ok": False, "error": "Nemáte oprávnění."}, status=403)

    value = (request.POST.get("value") or "").strip()

    if not value:

        return JsonResponse({"ok": False, "error": "Vyplňte název osoby."}, status=400)

    if len(value) > 255:

        return JsonResponse({"ok": False, "error": "Název je příliš dlouhý."}, status=400)

    obj, created = NameCatalog.objects.get_or_create(value=value)

    return JsonResponse(

        {

            "ok": True,

            "id": obj.pk,

            "value": obj.value,

            "created": created,

        }

    )

