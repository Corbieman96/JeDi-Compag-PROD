"""Oprávnění k úpravám požadavků na svoz z dashboardu."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.services.access import can_see_all_waste_docs
from users.services.sberny_dvur import can_create_svoz_request, get_sberny_dvur_subject
from waste_docs.models import SvozTask


def can_user_quick_edit_svoz_task(user: AbstractBaseUser, task: SvozTask) -> bool:
    if not user.is_authenticated or task.status != SvozTask.Status.OPEN:
        return False
    if can_see_all_waste_docs(user):
        return True
    if can_create_svoz_request(user):
        subj = get_sberny_dvur_subject(user)
        return bool(subj and subj.pk == task.subject_profile_id)
    return False
