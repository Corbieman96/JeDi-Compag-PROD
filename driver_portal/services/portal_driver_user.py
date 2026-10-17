"""Účet portálu pro řidiče: existující uživatel z linku, jinak deterministický účet bez hesla."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from catalogs.models import DriverProfile
from users.constants import ROLE_RIDIC
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label, set_user_role

User = get_user_model()


def username_portal_driver_auto(driver_pk: int) -> str:
    return f"portal_driver_{driver_pk}"


def get_or_attach_user_for_driver_portal(driver: DriverProfile):
    """
    Vrátí uživatele navázaného na tento DriverProfile pro portál.

    1) Pokud už někdo drží driver_profile v přístupovém profilu, použije se.
    2) Jinak get_or_create uživatele portal_driver_<pk> (bez hesla), role Řidič.
    """
    linked = (
        UserAccessProfile.objects.filter(driver_profile_id=driver.pk)
        .select_related("user")
        .first()
    )
    if linked:
        return linked.user

    uname = username_portal_driver_auto(driver.pk)
    user, created = User.objects.get_or_create(
        username=uname,
        defaults={
            "first_name": (driver.first_name or "")[:150],
            "last_name": (driver.last_name or "")[:150],
            "email": "",
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
        set_user_role(user, ROLE_RIDIC)
    else:
        patch = {}
        fn = (driver.first_name or "")[:150]
        ln = (driver.last_name or "")[:150]
        if user.first_name != fn:
            patch["first_name"] = fn
        if user.last_name != ln:
            patch["last_name"] = ln
        if patch:
            for k, v in patch.items():
                setattr(user, k, v)
            user.save(update_fields=list(patch.keys()))
        if get_user_role_label(user) != ROLE_RIDIC:
            set_user_role(user, ROLE_RIDIC)

    prof = get_access_profile(user)
    prof.driver_profile_id = driver.pk
    prof.save(update_fields=["driver_profile_id"])
    return user
