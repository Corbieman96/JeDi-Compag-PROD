"""Audit otevření matice sběrného dvora (Log SD) — bez alertů."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .record import SOURCE_OPEN

OPEN_THROTTLE_MINUTES = 15
MSG_MATRIX_READY = "Otevření matice — formulář připraven k odeslání"
MSG_MATRIX_CLOSED = "Otevření matice — dnes už uzavřeno (odesláno dříve)"


def record_matrix_open(
    *,
    subject: NameSubjectProfile,
    user: AbstractBaseUser,
    already_submitted_today: bool,
) -> int:
    """Zapíše otevření matice; max 1× / uživatel / dvůr / 15 min."""
    message = MSG_MATRIX_CLOSED if already_submitted_today else MSG_MATRIX_READY
    now = timezone.now()
    cutoff = now - timedelta(minutes=OPEN_THROTTLE_MINUTES)
    recent = YardSvozSubmitErrorLog.objects.filter(
        subject_profile=subject,
        created_by=user,
        source=SOURCE_OPEN,
        created_at__gte=cutoff,
        message=message,
    ).exists()
    if recent:
        return 0
    YardSvozSubmitErrorLog.objects.create(
        subject_profile=subject,
        submission_day=timezone.localdate(now),
        message=message,
        source=SOURCE_OPEN,
        created_by=user,
    )
    return 1
