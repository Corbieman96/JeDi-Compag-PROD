"""Log a přehled odeslaných řádků matice sběrného dvora pro /svoz-pozadavek/."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids
from waste_docs.models.yard_svoz_submission_log import YardSvozSubmissionLog
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine

HISTORY_UI_DAYS = 7
LOG_RETENTION_DAYS = 30


@dataclass(frozen=True)
class SubmissionLogDisplayRow:
    display_label: str
    waste_suffix_label: str
    container_numbers: str
    vehicle_kind_label: str
    yard_contact_note: str
    submitted_at_display: str
    created_by_label: str
    is_hazardous: bool
    target_date: date | None


def _user_display_label(user) -> str:
    if user is None:
        return "—"
    full = (getattr(user, "get_full_name", lambda: "")() or "").strip()
    if full:
        return full
    return (getattr(user, "username", None) or "—").strip() or "—"


def _waste_suffix_label_from_log(entry: YardSvozSubmissionLog) -> str:
    wt = getattr(entry, "waste_type", None)
    suf = getattr(entry, "suffix", None)
    parts = []
    if wt:
        code = (getattr(wt, "code", None) or "").strip()
        val = (getattr(wt, "value", None) or "").strip()
        parts.append(f"{val} ({code})" if code else val)
    if suf:
        parts.append((getattr(suf, "value", None) or "").strip())
    return " · ".join(p for p in parts if p) or "—"


def _log_to_display_row(entry: YardSvozSubmissionLog) -> SubmissionLogDisplayRow:
    vk = getattr(entry, "vehicle_kind", None)
    local_dt = timezone.localtime(entry.submitted_at)
    label = (entry.display_label or "").strip()
    if not label:
        label = _waste_suffix_label_from_log(entry)
    return SubmissionLogDisplayRow(
        display_label=label,
        waste_suffix_label=_waste_suffix_label_from_log(entry),
        container_numbers=(entry.container_numbers or "").strip() or "—",
        vehicle_kind_label=vk.display_label() if vk else "—",
        yard_contact_note=(entry.yard_contact_note or "").strip(),
        submitted_at_display=local_dt.strftime("%H:%M"),
        created_by_label=_user_display_label(entry.created_by),
        is_hazardous=bool(entry.is_hazardous),
        target_date=entry.target_date,
    )


def record_submission_log_line(
    *,
    pline: SvozPendingLine,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
    is_hazardous: bool = False,
    target_date: date | None = None,
    result_summary: str = "",
) -> YardSvozSubmissionLog:
    """Uloží snapshot řádku do textového logu (nezávisle na SvozTask)."""
    pair = pline.pair
    kind_ids = pair_vehicle_kind_ids(pair)
    vehicle_kind_id = kind_ids[0] if kind_ids else pair.yard_vehicle_kind_id
    now = timezone.now()
    return YardSvozSubmissionLog.objects.create(
        subject_profile=subject,
        submission_day=timezone.localdate(now),
        display_label=pline.matrix_display_label,
        waste_type_id=pair.waste_type_id,
        suffix_id=pair.suffix_id,
        container_numbers=pline.container_numbers,
        vehicle_kind_id=vehicle_kind_id,
        yard_contact_note=pline.yard_contact_note,
        is_hazardous=is_hazardous,
        result_summary=(result_summary or "").strip()[:300],
        target_date=target_date,
        created_by=user,
        source_waste_suffix_pair=pair,
    )


def yard_svoz_submissions_grouped(
    *,
    subject_profile_id: int,
    history_days: int = HISTORY_UI_DAYS,
    max_age_days: int = LOG_RETENTION_DAYS,
    now=None,
) -> dict:
    """
    Přehled logu pro dvůr: dnes + historie po dnech (včera … history_days zpět).

    Bez filtru created_by — vidí všichni uživatelé stejného subjektu.
    """
    today = timezone.localdate(now)
    min_day = today - timedelta(days=max_age_days - 1)
    history_start = today - timedelta(days=history_days)

    qs = (
        YardSvozSubmissionLog.objects.filter(
            subject_profile_id=int(subject_profile_id),
            submission_day__gte=min_day,
        )
        .select_related("waste_type", "suffix", "vehicle_kind", "created_by")
        .order_by("-submitted_at", "-pk")
    )

    today_rows: list[SubmissionLogDisplayRow] = []
    by_day: dict[date, list[SubmissionLogDisplayRow]] = {}

    for entry in qs:
        row = _log_to_display_row(entry)
        day = entry.submission_day
        if day == today:
            today_rows.append(row)
        elif history_start < day < today:
            by_day.setdefault(day, []).append(row)

    history_by_day = sorted(by_day.items(), key=lambda x: x[0], reverse=True)
    history_total_count = sum(len(rows) for _, rows in history_by_day)
    return {
        "today": today_rows,
        "history_by_day": history_by_day,
        "history_total_count": history_total_count,
    }


def purge_yard_svoz_submission_logs_older_than(*, retention_days: int = LOG_RETENTION_DAYS, now=None) -> int:
    """Smaže jen textový log starší než retention_days. Vrací počet smazaných řádků."""
    cutoff = timezone.localdate(now) - timedelta(days=int(retention_days))
    deleted, _ = YardSvozSubmissionLog.objects.filter(submission_day__lt=cutoff).delete()
    return int(deleted)


__all__ = [
    "HISTORY_UI_DAYS",
    "LOG_RETENTION_DAYS",
    "SubmissionLogDisplayRow",
    "purge_yard_svoz_submission_logs_older_than",
    "record_submission_log_line",
    "yard_svoz_submissions_grouped",
]
