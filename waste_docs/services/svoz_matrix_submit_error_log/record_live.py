"""Zápis chyb z živé AJAX kontroly kontejneru — bez změny validační logiky."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .record import SOURCE_LIVE


def record_live_validation_errors(
    *,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
    messages: list[str],
    display_label: str = "",
    container_numbers: str = "",
) -> int:
    """Uloží chyby z GET validate-container. Stejný dvůr + kontejner + text tentýž den znovu nezapisuje."""
    cleaned = [str(m).strip() for m in messages if str(m).strip()]
    if not cleaned:
        return 0
    now = timezone.now()
    day = timezone.localdate(now)
    label = (display_label or "").strip()[:200]
    containers = (container_numbers or "").strip()[:500]
    written = 0
    for text in cleaned:
        message = text[:4000]
        already = YardSvozSubmitErrorLog.objects.filter(
            subject_profile=subject,
            submission_day=day,
            source=SOURCE_LIVE,
            container_numbers=containers,
            message=message,
        ).exists()
        if already:
            continue
        YardSvozSubmitErrorLog.objects.create(
            subject_profile=subject,
            submission_day=day,
            message=message,
            source=SOURCE_LIVE,
            display_label=label,
            container_numbers=containers,
            created_by=user,
        )
        written += 1
    return written
