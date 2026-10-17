"""Data pro upozornění a modal na dashboardu dispečera — chyby + odeslání."""

from __future__ import annotations

from collections import OrderedDict

from django.utils import timezone

from waste_docs.models.yard_svoz_submission_log import YardSvozSubmissionLog
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .group_days import group_rows_by_day
from .query import display_row, dispatcher_alert_unread_count, has_any_rows
from .record import SOURCE_AUDIT_ONLY

# Limit řádků pro modal na dashboardu (každý typ zvlášť).
DASHBOARD_MODAL_ROW_LIMIT = 50


def _subject_label_from_profile(subject) -> str:
    subject_label = (getattr(subject, "company_name", None) or "").strip()
    if not subject_label and getattr(subject, "name", None) is not None:
        subject_label = (getattr(subject.name, "value", None) or "").strip()
    if not subject_label:
        subject_label = f"Dvůr #{subject.pk}"
    return subject_label


def _user_label(user) -> str:
    if user is None:
        return "—"
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    return full or (getattr(user, "username", None) or "—")


def display_sent_row(entry: YardSvozSubmissionLog) -> dict:
    local_dt = timezone.localtime(entry.submitted_at)
    subject = entry.subject_profile
    summary = (entry.result_summary or "").strip()
    if not summary:
        summary = (
            "Nebezpečný odpad — fronta dispečera"
            if entry.is_hazardous
            else "Odesláno"
        )
    return {
        "pk": entry.pk,
        "kind": "sent",
        "source": "sent",
        "subject_id": subject.pk,
        "subject_label": _subject_label_from_profile(subject),
        "created_at_display": local_dt.strftime("%d.%m. %H:%M"),
        "time_display": local_dt.strftime("%H:%M"),
        "message": summary,
        "show_message": summary != "Odesláno",
        "display_label": (entry.display_label or "").strip(),
        "container_numbers": (entry.container_numbers or "").strip(),
        "suffix_label": (getattr(getattr(entry, "suffix", None), "value", None) or "").strip(),
        "created_by_label": _user_label(entry.created_by),
        "is_unread": False,
        "can_delete": True,
        "delete_kind": "sent",
        "sort_at": entry.submitted_at,
    }


def dispatcher_error_log_badge() -> dict:
    """Jen počítadla pro masthead — bez načítání historie (rychlý dashboard GET)."""
    return {
        "yard_submit_error_unread_count": dispatcher_alert_unread_count(),
        "yard_submit_error_has_any": has_any_rows(),
        "yard_submit_error_groups": [],
    }


def dispatcher_error_log_dashboard(
    *,
    subject_profile_id: int | None = None,
    include_login: bool = False,
    row_limit: int | None = None,
) -> dict:
    unread = dispatcher_alert_unread_count()
    any_errors = has_any_rows()
    sent_qs = YardSvozSubmissionLog.objects.select_related(
        "subject_profile",
        "subject_profile__name",
        "created_by",
        "suffix",
    ).order_by("-submitted_at", "-pk")
    error_qs = YardSvozSubmitErrorLog.objects.select_related(
        "subject_profile",
        "subject_profile__name",
        "created_by",
    ).order_by("-created_at", "-pk")
    if not include_login:
        error_qs = error_qs.exclude(source__in=SOURCE_AUDIT_ONLY)
    if subject_profile_id is not None:
        sent_qs = sent_qs.filter(subject_profile_id=subject_profile_id)
        error_qs = error_qs.filter(subject_profile_id=subject_profile_id)
        # Stránka logu jednoho dvoru — původní řazení podle jména není potřeba.
    else:
        # Dashboard modal: nejnovější napříč dvory; limit ořízne starou historii.
        pass
    if row_limit is not None:
        sent_qs = sent_qs[:row_limit]
        error_qs = error_qs[:row_limit]

    by_subject: OrderedDict[int, dict] = OrderedDict()

    def _ensure(sid: int, label: str) -> dict:
        if sid not in by_subject:
            by_subject[sid] = {
                "subject_id": sid,
                "subject_label": label,
                "rows": [],
                "unread_count": 0,
            }
        return by_subject[sid]

    if any_errors or subject_profile_id is not None:
        for entry in error_qs:
            row = display_row(entry)
            group = _ensure(row["subject_id"], row["subject_label"])
            group["rows"].append(row)
            if row["is_unread"]:
                group["unread_count"] += 1

    for entry in sent_qs:
        row = display_sent_row(entry)
        group = _ensure(row["subject_id"], row["subject_label"])
        group["rows"].append(row)

    for group in by_subject.values():
        group["rows"].sort(
            key=lambda r: (r.get("sort_at"), r.get("pk") or 0),
            reverse=True,
        )
        group["days"] = group_rows_by_day(group["rows"])

    # Stabilní pořadí skupin podle názvu dvoru.
    groups = sorted(
        by_subject.values(),
        key=lambda g: ((g.get("subject_label") or "").lower(), g.get("subject_id") or 0),
    )

    return {
        "yard_submit_error_unread_count": unread,
        "yard_submit_error_has_any": any_errors,
        "yard_submit_error_groups": groups,
    }
