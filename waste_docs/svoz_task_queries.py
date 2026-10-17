"""Dotazy na otevřené požadavky na svoz pro dashboard a formulář průvodky."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.services.access import can_see_all_waste_docs
from users.services.sberny_dvur import get_sberny_dvur_subject, is_sberny_dvur_role
from waste_docs.models import SvozTask


def svoz_tasks_open_for_date(user: AbstractBaseUser, day) -> list[SvozTask]:
    qs = (
        SvozTask.objects.filter(target_date=day, status=SvozTask.Status.OPEN)
        .select_related(
            "subject_profile",
            "subject_profile__name",
            "waste_type",
            "suffix",
            "vehicle_kind",
            "activity",
            "created_by",
            "assigned_driver",
            "assigned_vehicle_rz",
        )
        .order_by("created_at", "pk")
    )
    if can_see_all_waste_docs(user):
        return list(qs)
    if is_sberny_dvur_role(user):
        subj = get_sberny_dvur_subject(user)
        return list(qs.filter(subject_profile=subj)) if subj else []
    return []

