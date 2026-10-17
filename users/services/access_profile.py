from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.models import UserAccessProfile

_PROFILE_CACHE_ATTR = "_jedi_access_profile_cache"


def get_access_profile(user: AbstractBaseUser) -> UserAccessProfile:
    """Vrátí nebo vytvoří profil přístupu pro daného uživatele (cache na instanci user)."""
    cached = getattr(user, _PROFILE_CACHE_ATTR, None)
    if cached is not None:
        return cached
    prof, _ = UserAccessProfile.objects.get_or_create(user=user)
    setattr(user, _PROFILE_CACHE_ATTR, prof)
    return prof
