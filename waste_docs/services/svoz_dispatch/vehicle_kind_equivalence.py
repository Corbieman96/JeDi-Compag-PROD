"""Sjednocení více řádků VehicleKindCatalog při párování plán dvora ↔ matice (bez slučování jen podle náhodné zkratky)."""

from __future__ import annotations

import unicodedata
from functools import lru_cache

from catalogs.models import VehicleKindCatalog

# Sloučení podle „stejného“ názvu jen při dostatečné délce — krátké názvy jde snad omylem zkopírovat u nesouvisejících druhů.
_NAME_BUCKET_MIN_LEN = 3


def vehicle_kind_catalog_name_normalized(name: str) -> str:
    s = (name or "").strip()
    nk = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in nk if unicodedata.category(ch) != "Mn").casefold()


def _bucket_key_for_vehicle_kind_row(vk: VehicleKindCatalog) -> tuple[str, str | int]:
    nm = vehicle_kind_catalog_name_normalized(vk.name or "")
    if len(nm) >= _NAME_BUCKET_MIN_LEN:
        return ("name", nm)
    sc = (vk.shortcut or "").strip().casefold()
    if sc:
        return ("sc", sc)
    return ("id", int(vk.pk))


@lru_cache(maxsize=512)
def equivalent_vehicle_kind_ids_for_plan_matching(reference_kind_id: int) -> tuple[int, ...]:
    """
    FK druhů vozidel, které aplikace považuje za zaměnitelné při hledání řádků plánu / profilů RZ.

    Pravidla: stejný slug názvu (bez diakritiky, min délky), případně jen shodná ``shortcut`` ve zbytku
    řádků (ve vaší DB je shortcut unikátní → typicky jen jedna PK).

    Používá se pro situace, kde matice odkazuje na jiný záznam řádku ``VehicleKindCatalog`` než řádek
    uloženého plánu, ale lidsky jde o totéž („Řetez“ vs „Řetěz“ aj.).
    """
    rid = int(reference_kind_id)
    ref = VehicleKindCatalog.objects.only("pk", "name", "shortcut").filter(pk=rid).first()
    if not ref:
        return ()
    key = _bucket_key_for_vehicle_kind_row(ref)

    matched: list[int] = []
    for vk in VehicleKindCatalog.objects.only("pk", "name", "shortcut"):
        if _bucket_key_for_vehicle_kind_row(vk) == key:
            matched.append(int(vk.pk))

    return tuple(sorted(set(matched)))


def clear_vehicle_kind_equivalence_cache() -> None:
    equivalent_vehicle_kind_ids_for_plan_matching.cache_clear()


def equivalent_vehicle_kind_ids_for_yard(
    subject_profile_id: int,
    reference_kind_id: int,
) -> tuple[int, ...]:
    """
    Ekvivalentní druhy vozidel pro párování plán ↔ matice u jednoho dvora.

    Zahrnuje globální ekvivalenci názvu/zkratky a navíc druhy z matice téhož dvora,
    které jsou navzájem v téže ekvivalence třídě (např. dva záznamy v číselníku pro stejný význam).
    """
    from catalogs.models import NameSubjectWasteSuffixPair

    ref_set = set(equivalent_vehicle_kind_ids_for_plan_matching(reference_kind_id))
    if not ref_set:
        return ()

    yard_ids: list[int] = []
    pairs = NameSubjectWasteSuffixPair.objects.filter(
        subject_profile_id=subject_profile_id,
        yard_svoz_enabled=True,
    ).prefetch_related("yard_vehicle_kinds")
    for pair in pairs:
        yard_ids.extend(int(x) for x in pair.yard_vehicle_kinds.values_list("pk", flat=True))
        if pair.yard_vehicle_kind_id:
            yard_ids.append(int(pair.yard_vehicle_kind_id))
    yard_ids = list(dict.fromkeys(yard_ids))
    out = set(ref_set)
    for vk_id in yard_ids:
        if vk_id in ref_set:
            continue
        if set(equivalent_vehicle_kind_ids_for_plan_matching(vk_id)) & ref_set:
            out.add(vk_id)
    return tuple(sorted(out))
