"""Čtení chybového logu — vždy filtrované na jeden dvůr, nebo seskupené pro dispečera."""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .record import SOURCE_LIVE, SOURCE_LOGIN, SOURCE_NON_ALERT, SOURCE_OPEN, SOURCE_SESSION, SOURCE_AUDIT_ONLY, YARD_PAGE_LIMIT


def _base_qs() -> QuerySet[YardSvozSubmitErrorLog]:
    return YardSvozSubmitErrorLog.objects.select_related(
        "subject_profile",
        "subject_profile__name",
        "created_by",
    )


def rows_for_subject(*, subject_profile_id: int, limit: int = YARD_PAGE_LIMIT) -> list[YardSvozSubmitErrorLog]:
    """Řádky pro panel chyb na matici SD — bez přihlášení/otevření/relace (to je v Log SD)."""
    return list(
        _base_qs()
        .filter(subject_profile_id=subject_profile_id)
        .exclude(source__in=SOURCE_AUDIT_ONLY)
        .order_by("-created_at", "-pk")[:limit]
    )


def unread_count() -> int:
    return YardSvozSubmitErrorLog.objects.filter(
        acknowledged_at__isnull=True,
    ).exclude(source__in=SOURCE_NON_ALERT).count()


def has_any_rows() -> bool:
    """Jsou nějaké chyby odeslání (ne audit) — pro tlačítko na dashboardu."""
    return YardSvozSubmitErrorLog.objects.exclude(source__in=SOURCE_AUDIT_ONLY).exists()


def subject_ids_with_success_on(day) -> set[int]:
    """Dvory, které v daný den úspěšně odeslaly aspoň jeden řádek matice."""
    from waste_docs.models.yard_svoz_submission_log import YardSvozSubmissionLog

    return set(
        YardSvozSubmissionLog.objects.filter(submission_day=day).values_list(
            "subject_profile_id",
            flat=True,
        )
    )


def dispatcher_alert_unread_count(*, day=None) -> int:
    """Nepřečtené chyby odeslání dnes u dvorů, které dnes ještě neodeslaly svoz (ne živá kontrola)."""
    day = day or timezone.localdate()
    success_ids = subject_ids_with_success_on(day)
    qs = YardSvozSubmitErrorLog.objects.filter(
        acknowledged_at__isnull=True,
        submission_day=day,
    ).exclude(source__in=SOURCE_NON_ALERT)
    if success_ids:
        qs = qs.exclude(subject_profile_id__in=success_ids)
    return qs.count()


def display_row(entry: YardSvozSubmitErrorLog) -> dict:
    local_dt = timezone.localtime(entry.created_at)
    user = entry.created_by
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    user_label = full or (getattr(user, "username", None) or "—")
    subject = entry.subject_profile
    subject_label = (getattr(subject, "company_name", None) or "").strip()
    if not subject_label and getattr(subject, "name", None) is not None:
        subject_label = (getattr(subject.name, "value", None) or "").strip()
    if not subject_label:
        subject_label = f"Dvůr #{subject.pk}"
    source = (getattr(entry, "source", None) or "submit").strip() or "submit"
    is_live = source == SOURCE_LIVE
    is_login = source == SOURCE_LOGIN
    is_open = source == SOURCE_OPEN
    is_session = source == SOURCE_SESSION
    kind = (
        "login"
        if is_login
        else ("open" if is_open else ("session" if is_session else "error"))
    )
    return {
        "pk": entry.pk,
        "kind": kind,
        "source": source,
        "subject_id": subject.pk,
        "subject_label": subject_label,
        "created_at_display": local_dt.strftime("%d.%m. %H:%M"),
        "time_display": local_dt.strftime("%H:%M"),
        "message": entry.message,
        "show_message": bool((entry.message or "").strip()) and not is_login,
        "display_label": (entry.display_label or "").strip(),
        "container_numbers": (entry.container_numbers or "").strip(),
        "suffix_label": "",
        "created_by_label": user_label,
        "is_unread": entry.acknowledged_at is None
        and not is_live
        and not is_login
        and not is_open
        and not is_session,
        "can_delete": True,
        "delete_kind": "error",
        "sort_at": entry.created_at,
    }
