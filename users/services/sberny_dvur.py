"""Role Sběrný dvůr — vazba na subjekt v číselníku a oprávnění k požadavkům."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.access import app_role, can_see_all_waste_docs
from users.services.access_profile import get_access_profile


def get_sberny_dvur_subject(user: AbstractBaseUser):
    """NameSubjectProfile přiřazený uživateli v přístupovém profilu, nebo None."""
    if not user.is_authenticated:
        return None
    prof = get_access_profile(user)
    return prof.sberny_dvur_subject


def is_sberny_dvur_role(user: AbstractBaseUser) -> bool:
    return bool(user.is_authenticated and app_role(user) == ROLE_SBERNY_DVUR)


def can_create_svoz_request(user: AbstractBaseUser) -> bool:
    if not user.is_authenticated:
        return False
    if is_sberny_dvur_role(user):
        return get_sberny_dvur_subject(user) is not None
    return can_see_all_waste_docs(user) and get_sberny_dvur_subject(user) is not None


def can_link_pruvodka_from_svoz_task(user: AbstractBaseUser) -> bool:
    """Dispečer / Admin mohou z úkolu založit průvodku s předvyplněním."""
    from users.services.waste_doc_permissions import can_create_pruvodka

    if not can_create_pruvodka(user):
        return False
    return can_see_all_waste_docs(user)
