"""Ruční přepnutí uzavření dne pro zákaznické požadavky (dispečer)."""

from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from users.services.access import can_see_all_waste_docs
from waste_docs.services.customer_request_date_closure import toggle_manual_closure


@login_required
@require_POST
def customer_request_closure_toggle(request):
    if not can_see_all_waste_docs(request.user):
        raise Http404("Stránka neexistuje.")

    date_raw = (request.POST.get("date") or "").strip()
    try:
        closure_day = date.fromisoformat(date_raw)
    except ValueError as exc:
        raise Http404("Neplatné datum.") from exc

    is_closed = toggle_manual_closure(request.user, closure_day)
    if is_closed:
        messages.success(
            request,
            f"Zadávání požadavků pro {closure_day.strftime('%d.%m.%Y')} bylo uzavřeno.",
        )
    else:
        messages.success(
            request,
            f"Zadávání požadavků pro {closure_day.strftime('%d.%m.%Y')} bylo znovu otevřeno.",
        )
    return redirect(f"{reverse('core:dashboard')}?date={closure_day.isoformat()}")
