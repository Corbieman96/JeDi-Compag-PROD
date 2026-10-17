from __future__ import annotations

from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from day_reminders.models import DayReminder
from day_reminders.services import actions
from day_reminders.card_colors import normalize_card_color
from day_reminders.services.monthly_recurrence import parse_monthly_rule_from_post
from users.services.access import can_manage_dashboard_notes


def _dash_url(d: date) -> str:
    return f"{reverse('core:dashboard')}?date={d.isoformat()}"


def _parse_date_required(key: str, post) -> date:
    raw = (post.get(key) or "").strip()
    if not raw:
        raise ValueError("Chybí datum.")
    return date.fromisoformat(raw)


def _parse_date_optional(key: str, post) -> date | None:
    raw = (post.get(key) or "").strip()
    if not raw:
        return None
    return date.fromisoformat(raw)


def _context_date_from_request(request) -> date:
    """Datum dashboardu z POST/GET; po přihlášení (GET na complete) typicky dnešek."""
    src = request.POST if request.method == "POST" else request.GET
    raw = (src.get("context_date") or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return timezone.localdate()


def _redirect_if_cannot_manage_notes(request, d_context: date):
    if not can_manage_dashboard_notes(request.user):
        messages.error(request, "Nemáte oprávnění upravovat denní poznámky na dashboardu.")
        return redirect(_dash_url(d_context))
    return None


def _parse_repeat_weekdays(post) -> list[int]:
    out: list[int] = []
    for x in post.getlist("repeat_weekdays"):
        try:
            n = int(x)
            if 0 <= n <= 6:
                out.append(n)
        except (TypeError, ValueError):
            pass
    return sorted(set(out))


@login_required
@require_POST
def reminder_create(request):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    try:
        kind = (request.POST.get("kind") or "").strip()
        title = request.POST.get("title") or ""
        text = request.POST.get("text") or ""
        pinned = _parse_date_optional("pinned_date", request.POST)
        rdays = _parse_repeat_weekdays(request.POST)
        monthly_rule = (
            parse_monthly_rule_from_post(request.POST) if kind == "monthly" else None
        )
        raf = _parse_date_optional("repeat_active_from", request.POST)
        rau = _parse_date_optional("repeat_active_until", request.POST)
        rstart = _parse_date_optional("rolling_start", request.POST)
        if kind == "rolling" and rstart is None:
            rstart = d_context
        actions.create_reminder(
            user=request.user,
            title=title,
            text=text,
            kind=kind,
            pinned_date=pinned or (d_context if kind == "one_off" else None),
            repeat_weekdays=rdays if kind == "weekly" else None,
            repeat_monthly=monthly_rule,
            repeat_active_from=raf,
            repeat_active_until=rau,
            rolling_start=rstart,
            card_color=normalize_card_color(request.POST.get("card_color")),
            note_group=request.POST.get("note_group"),
        )
        messages.success(request, "Poznámka byla přidána.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e) or "Neplatná data.")
    return redirect(_dash_url(d_context))


@login_required
def reminder_complete(request, pk: int):
    if request.method != "POST":
        d_context = _context_date_from_request(request)
        messages.info(
            request,
            "Označení poznámky proveďte znovu z dashboardu (tlačítko po přihlášení nebo obnovení stránky neuloží stav).",
        )
        return redirect(_dash_url(d_context))
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    try:
        reminder = DayReminder.objects.filter(pk=pk).only("kind").first()
        resolved_now = actions.toggle_reminder_completion_for_day(pk, d_context, request.user)
        is_rolling = reminder and reminder.kind == DayReminder.Kind.ROLLING
        if resolved_now:
            if is_rolling:
                messages.success(request, "Poznámka je vyřešená.")
            else:
                messages.success(request, "Poznámka je vyřešená pro tento den.")
        elif is_rolling:
            messages.success(request, "Vyřešení bylo zrušeno.")
        else:
            messages.success(request, "Vyřešení pro tento den bylo zrušeno.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(_dash_url(d_context))


@login_required
@require_POST
def reminder_snooze(request, pk: int):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    try:
        until = _parse_date_required("snoozed_until", request.POST)
        n = actions.snooze_reminder(pk, until)
        if n:
            messages.success(request, "Poznámka byla odložena.")
        else:
            messages.warning(request, "Poznámku nelze odložit.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e) or "Neplatné datum.")
    return redirect(_dash_url(d_context))


@login_required
@require_POST
def reminder_exception(request, pk: int):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    try:
        original = _parse_date_required("original_date", request.POST)
        target = _parse_date_required("rescheduled_to", request.POST)
        actions.add_weekly_exception(pk, original, target)
        messages.success(request, "Výjimka přesunu byla uložena.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(_dash_url(d_context))


@login_required
@require_POST
def reminder_update(request, pk: int):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    try:
        title = (request.POST.get("title") or "").strip()
        text = (request.POST.get("text") or "").strip()
        pinned = _parse_date_optional("pinned_date", request.POST)
        rdays = _parse_repeat_weekdays(request.POST)
        reminder = DayReminder.objects.filter(pk=pk).only("kind").first()
        monthly_rule = None
        if reminder and reminder.kind == DayReminder.Kind.MONTHLY:
            monthly_rule = parse_monthly_rule_from_post(request.POST)
        raf = _parse_date_optional("repeat_active_from", request.POST)
        rau = _parse_date_optional("repeat_active_until", request.POST)
        rstart = _parse_date_optional("rolling_start", request.POST)
        actions.update_reminder(
            pk,
            title=title,
            text=text,
            pinned_date=pinned,
            repeat_weekdays=rdays,
            repeat_monthly=monthly_rule,
            repeat_active_from=raf,
            repeat_active_until=rau,
            rolling_start=rstart,
            card_color=normalize_card_color(request.POST.get("card_color")),
            note_group=request.POST.get("note_group"),
        )
        messages.success(request, "Poznámka byla uložena.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect(_dash_url(d_context))


@login_required
@require_POST
def reminder_delete(request, pk: int):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    n = actions.delete_reminder(pk)
    if n:
        messages.success(request, "Poznámka byla smazána.")
    else:
        messages.warning(request, "Poznámka neexistuje.")
    return redirect(_dash_url(d_context))


@login_required
@require_POST
def reminder_purge(request):
    d_context = _parse_date_required("context_date", request.POST)
    deny = _redirect_if_cannot_manage_notes(request, d_context)
    if deny:
        return deny
    confirm = request.POST.get("confirm_purge") == "1"
    if not confirm:
        messages.error(request, "Potvrďte promazání zaškrtnutím políčka.")
        return redirect(_dash_url(d_context))
    mode = (request.POST.get("purge_mode") or "").strip()
    try:
        if mode == "all_completed":
            n = actions.purge_completed(all_completed=True)
            messages.success(request, f"Smazáno dokončených záznamů: {n}.")
        elif mode == "completed_before":
            cutoff = _parse_date_required("completed_before", request.POST)
            n = actions.purge_completed(all_completed=False, completed_before=cutoff)
            messages.success(request, f"Smazáno starších dokončených záznamů: {n}.")
        elif mode == "stale_weekly":
            n = actions.purge_stale_weekly_ended()
            messages.success(request, f"Smazáno ukončených týdenních sérií: {n}.")
        else:
            messages.error(request, "Neplatný režim promazání.")
    except (ValueError, TypeError) as e:
        messages.error(request, str(e) or "Neplatná data.")
    return redirect(_dash_url(d_context))
