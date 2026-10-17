"""Stažení schválení požadavku z dispatch fronty."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_dispatcher_withdraw import (
    DispatcherWithdrawError,
    withdraw_from_dispatch,
)

from .common import can_dispatcher_review


@login_required
@require_POST
def customer_request_dispatch_withdraw(request, pk: int):
    if not can_dispatcher_review(request.user):
        messages.error(request, "Nemáte oprávnění ke stažení schválení.")
        return redirect("waste_docs:customer_request_detail", pk=pk)

    item = get_object_or_404(CustomerRequest, pk=pk)
    action = (request.POST.get("action") or "").strip()
    note = (request.POST.get("note") or "").strip()

    try:
        withdraw_from_dispatch(item=item, actor=request.user, action=action, note=note)
    except DispatcherWithdrawError as exc:
        messages.error(request, str(exc))
        return redirect("waste_docs:customer_request_detail", pk=pk)

    if action == "return":
        messages.success(request, "Požadavek byl vrácen zadavateli k opravě a zmizel z dispatch fronty.")
    else:
        messages.success(request, "Požadavek byl zrušen a zmizel z dispatch fronty.")

    return redirect("waste_docs:customer_request_detail", pk=pk)
