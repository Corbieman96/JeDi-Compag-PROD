"""Zápis vypršení přihlášení uživatele sběrného dvora do Log SD."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .record import SOURCE_SESSION

MSG_IDLE = "Přihlášení vypršelo kvůli nečinnosti — je nutné se znovu přihlásit"
MSG_LIFETIME = "Přihlášení vypršelo (maximální délka relace) — je nutné se znovu přihlásit"


def record_yard_session_expired(*, user: AbstractBaseUser, reason: str = "idle") -> int:
    """Uloží vypršení relace jen u role Sběrný dvůr s subjektem. Jinak 0. Nesmí shodit middleware."""
    try:
        from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role

        if not is_sberny_dvur_role(user):
            return 0
        subject = get_sberny_dvur_subject(user)
        if subject is None:
            return 0
        message = MSG_LIFETIME if reason == "lifetime" else MSG_IDLE
        now = timezone.now()
        YardSvozSubmitErrorLog.objects.create(
            subject_profile=subject,
            submission_day=timezone.localdate(now),
            message=message,
            source=SOURCE_SESSION,
            created_by=user,
        )
        return 1
    except Exception:
        return 0
