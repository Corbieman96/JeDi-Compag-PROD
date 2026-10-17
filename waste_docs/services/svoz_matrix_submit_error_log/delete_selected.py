"""Mazání vybraných dnů a řádků Log SD (chyby i odeslání)."""

from __future__ import annotations

from datetime import date, datetime

from waste_docs.models.yard_svoz_submission_log import YardSvozSubmissionLog
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .reclaim_space import reclaim_sqlite_space_after_delete


def _parse_ids(raw_values: list[str]) -> set[int]:
    out: set[int] = set()
    for raw in raw_values:
        text = str(raw).strip()
        if text.isdigit():
            out.add(int(text))
    return out


def _parse_days(raw_values: list[str]) -> list[date]:
    days: list[date] = []
    seen: set[date] = set()
    for raw in raw_values:
        text = str(raw).strip()
        try:
            day = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day not in seen:
            seen.add(day)
            days.append(day)
    return days


def delete_selected(
    *,
    subject_profile_id: int,
    error_pks: list[str] | None = None,
    sent_pks: list[str] | None = None,
    day_isos: list[str] | None = None,
) -> int:
    """Smaže zaškrtnuté řádky a celé zaškrtnuté dny u daného dvora. Vrací počet smazaných."""
    error_ids = _parse_ids(error_pks or [])
    sent_ids = _parse_ids(sent_pks or [])
    days = _parse_days(day_isos or [])
    if days:
        error_ids |= set(
            YardSvozSubmitErrorLog.objects.filter(
                subject_profile_id=subject_profile_id,
                submission_day__in=days,
            ).values_list("pk", flat=True)
        )
        sent_ids |= set(
            YardSvozSubmissionLog.objects.filter(
                subject_profile_id=subject_profile_id,
                submission_day__in=days,
            ).values_list("pk", flat=True)
        )
    deleted = 0
    if error_ids:
        n, _ = YardSvozSubmitErrorLog.objects.filter(
            subject_profile_id=subject_profile_id,
            pk__in=error_ids,
        ).delete()
        deleted += int(n)
    if sent_ids:
        n, _ = YardSvozSubmissionLog.objects.filter(
            subject_profile_id=subject_profile_id,
            pk__in=sent_ids,
        ).delete()
        deleted += int(n)
    if deleted:
        reclaim_sqlite_space_after_delete()
    return deleted
