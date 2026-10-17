"""Zápis chyb odeslání — volá se z view až po collect/submit, nemění jejich logiku."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

YARD_PAGE_LIMIT = 80
SOURCE_SUBMIT = YardSvozSubmitErrorLog.Source.SUBMIT
SOURCE_LIVE = YardSvozSubmitErrorLog.Source.LIVE
SOURCE_LOGIN = YardSvozSubmitErrorLog.Source.LOGIN
SOURCE_OPEN = YardSvozSubmitErrorLog.Source.OPEN
SOURCE_SESSION = YardSvozSubmitErrorLog.Source.SESSION
# Audit / info — nepočítají se do alertu „Chyby SD“.
SOURCE_NON_ALERT = (SOURCE_LIVE, SOURCE_LOGIN, SOURCE_OPEN, SOURCE_SESSION)
# Skryté v panelu chyb na matici; viditelné v Log SD dvoru (include_login).
SOURCE_AUDIT_ONLY = (SOURCE_LOGIN, SOURCE_OPEN, SOURCE_SESSION)


def record_error_messages(
    *,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
    messages: list[str],
    display_label: str = "",
    container_numbers: str = "",
    source: str = SOURCE_SUBMIT,
) -> int:
    """Uloží texty chyb k danému dvoru. Prázdný seznam nic nezapisuje."""
    cleaned = [str(m).strip() for m in messages if str(m).strip()]
    if not cleaned:
        return 0
    now = timezone.now()
    day = timezone.localdate(now)
    label = (display_label or "").strip()[:200]
    containers = (container_numbers or "").strip()[:500]
    src = (source or SOURCE_SUBMIT).strip() or SOURCE_SUBMIT
    rows = [
        YardSvozSubmitErrorLog(
            subject_profile=subject,
            submission_day=day,
            message=text[:4000],
            source=src,
            display_label=label,
            container_numbers=containers,
            created_by=user,
        )
        for text in cleaned
    ]
    YardSvozSubmitErrorLog.objects.bulk_create(rows)
    return len(rows)
