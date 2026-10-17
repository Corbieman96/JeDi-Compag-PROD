"""Kompatibilita druhů vozidel (strom parent_kind + M2M) pro svoz, RZ a pasporty."""

from __future__ import annotations

from functools import lru_cache

from catalogs.models import VehicleKindCatalog


def clear_vehicle_kind_compatibility_cache() -> None:
    compatible_kind_ids.cache_clear()
    _ancestor_ids.cache_clear()
    _descendant_ids.cache_clear()


@lru_cache(maxsize=512)
def _ancestor_ids(kind_id: int) -> frozenset[int]:
    out: set[int] = set()
    current = (
        VehicleKindCatalog.objects.filter(pk=kind_id)
        .values_list("parent_kind_id", flat=True)
        .first()
    )
    seen: set[int] = {int(kind_id)}
    while current:
        pid = int(current)
        if pid in seen:
            break
        seen.add(pid)
        out.add(pid)
        current = (
            VehicleKindCatalog.objects.filter(pk=pid)
            .values_list("parent_kind_id", flat=True)
            .first()
        )
    return frozenset(out)


@lru_cache(maxsize=512)
def _descendant_ids(kind_id: int) -> frozenset[int]:
    out: set[int] = set()
    frontier = [int(kind_id)]
    seen: set[int] = set(frontier)
    while frontier:
        parent = frontier.pop()
        child_pks = list(
            VehicleKindCatalog.objects.filter(parent_kind_id=parent).values_list("pk", flat=True)
        )
        for cid in child_pks:
            cid = int(cid)
            if cid in seen:
                continue
            seen.add(cid)
            out.add(cid)
            frontier.append(cid)
    return frozenset(out)


@lru_cache(maxsize=512)
def compatible_kind_ids(reference_kind_id: int) -> frozenset[int]:
    """
    Druhy vozidel, které mohou obsloužit požadavek / řádek s druhem ``reference_kind_id``.

    reference + všichni předci + všichni potomci + extra_compatible_kinds (M2M).
    """
    rid = int(reference_kind_id)
    out: set[int] = {rid}
    out |= _ancestor_ids(rid)
    out |= _descendant_ids(rid)
    extra = VehicleKindCatalog.objects.filter(pk=rid).values_list(
        "extra_compatible_kinds__pk", flat=True
    )
    for eid in extra:
        if eid:
            out.add(int(eid))
    return frozenset(out)


def profile_vehicle_kind_ids(profile) -> set[int]:
    if profile is None:
        return set()
    return {int(k.pk) for k in profile.vehicle_kinds.all()}


def follow_up_covers_parent_kind(parent_kind_id: int, follow_kind_id: int) -> bool:
    """
    Navazující druh může stáhnout, co přistavil rodič — stejný druh nebo potomek ve stromu.

    Silnější vozidlo (např. 3H) může stáhnout H; H nestačí na 3H.
    """
    pid, fid = int(parent_kind_id), int(follow_kind_id)
    if pid == fid:
        return True
    return fid in _descendant_ids(pid)


def follow_up_allowed_kind_ids(parent_kind_id: int) -> frozenset[int]:
    """Druhy vozidel přípustné pro 2. část jízdy po daném druhu v 1. části."""
    pid = int(parent_kind_id)
    out: set[int] = {pid}
    out |= _descendant_ids(pid)
    return frozenset(out)


def vehicle_kind_covers_task(task_kind_id: int, vehicle_kind_id: int) -> bool:
    """Směrově: vozidlo ``vehicle_kind_id`` může obsloužit úkol ``task_kind_id`` (strom parent_kind)."""
    return follow_up_covers_parent_kind(int(task_kind_id), int(vehicle_kind_id))


def vehicle_kinds_covering_task(task_kind_id: int) -> frozenset[int]:
    """Druhy vozidel, které směrově pokrývají požadovaný druh úkolu."""
    return follow_up_allowed_kind_ids(int(task_kind_id))


def rz_profile_serves_task_kind(profile, task_kind_id: int | None) -> bool:
    if not profile or not task_kind_id:
        return False
    task_id = int(task_kind_id)
    return any(
        vehicle_kind_covers_task(task_id, vk_id) for vk_id in profile_vehicle_kind_ids(profile)
    )


def passport_kind_valid_for_task(passport_kind_id: int | None, task_kind_id: int | None) -> bool:
    if not passport_kind_id or not task_kind_id:
        return True
    return vehicle_kind_covers_task(int(task_kind_id), int(passport_kind_id))


def rz_profile_covers_passport_kind(profile, passport_kind_id: int | None) -> bool:
    """RZ profil může vést kontejner s pasportem daného druhu (bez kontextu řádku matice)."""
    if not profile or not passport_kind_id:
        return True
    passport_id = int(passport_kind_id)
    return any(
        vehicle_kind_covers_task(passport_id, vk_id) for vk_id in profile_vehicle_kind_ids(profile)
    )


def passport_matches_vehicle_rz_compat(
    passport,
    vehicle_rz,
    *,
    task_kind_id: int | None = None,
) -> bool:
    """
    Pasport a RZ jsou slučitelné.

    S ``task_kind_id`` (řádek matice / úkol): obojí musí sedět do compatible(task_kind_id).
    Bez něj: profil RZ musí pokrýt druh uvedený na pasportu (strom + M2M od pasportu).
    """
    if passport is None or vehicle_rz is None:
        return True
    from django.core.exceptions import ObjectDoesNotExist

    try:
        prof = vehicle_rz.profile
    except ObjectDoesNotExist:
        return False

    pk = getattr(passport, "vehicle_kind_id", None)
    if task_kind_id:
        if not passport_kind_valid_for_task(pk, task_kind_id):
            return False
        return rz_profile_serves_task_kind(prof, task_kind_id)
    return rz_profile_covers_passport_kind(prof, pk)


__all__ = [
    "clear_vehicle_kind_compatibility_cache",
    "compatible_kind_ids",
    "follow_up_allowed_kind_ids",
    "follow_up_covers_parent_kind",
    "passport_kind_valid_for_task",
    "passport_matches_vehicle_rz_compat",
    "rz_profile_covers_passport_kind",
    "rz_profile_serves_task_kind",
    "vehicle_kind_covers_task",
    "vehicle_kinds_covering_task",
]
