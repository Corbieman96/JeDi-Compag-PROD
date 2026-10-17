from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from day_reminders.note_print.queryset import reminders_for_print
from day_reminders.note_print.scope import SCOPE_CHOICES, parse_print_scope, scope_label


def _parse_day(raw: str | None) -> date:
    value = (raw or "").strip()
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        return timezone.localdate()


@login_required
def print_day_notes(request):
    day = _parse_day(request.GET.get("date"))
    scope = parse_print_scope(request.GET.get("scope"))
    rows = reminders_for_print(day, scope)
    return render(
        request,
        "day_reminders/note_print/print_day.html",
        {
            "page_title": "Tisk poznámek",
            "print_day": day,
            "print_scope": scope,
            "print_scope_label": scope_label(scope),
            "print_scope_choices": SCOPE_CHOICES,
            "reminders": rows,
            "auto_print": (request.GET.get("auto") or "").strip() == "1",
        },
    )
