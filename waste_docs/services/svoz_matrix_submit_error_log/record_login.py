"""Zápis přihlášení uživatele sběrného dvora do Log SD."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

from waste_docs.models.yard_svoz_submit_error_log import YardSvozSubmitErrorLog

from .record import SOURCE_LOGIN

LOGIN_MESSAGE = "Přihlášení do sběrného dvora"


def record_yard_login(*, user: AbstractBaseUser) -> int:
    """Uloží přihlášení jen u role Sběrný dvůr s přiřazeným subjektem. Jinak 0."""
    from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role

    if not is_sberny_dvur_role(user):
        return 0
    subject = get_sberny_dvur_subject(user)
    if subject is None:
        return 0
    now = timezone.now()
    YardSvozSubmitErrorLog.objects.create(
        subject_profile=subject,
        submission_day=timezone.localdate(now),
        message=LOGIN_MESSAGE,
        source=SOURCE_LOGIN,
        created_by=user,
    )
    return 1
