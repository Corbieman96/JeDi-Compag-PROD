"""Druhy vozidel u páru subjekt–odpad (matice svozu) — jeden nebo více."""

from __future__ import annotations

from catalogs.models import NameSubjectWasteSuffixPair, VehicleKindCatalog


def pair_vehicle_kind_queryset(pair: NameSubjectWasteSuffixPair):
    return pair.yard_vehicle_kinds.order_by("sort_order", "name", "pk")


def pair_vehicle_kind_ids(pair: NameSubjectWasteSuffixPair) -> list[int]:
    ids = [int(x) for x in pair_vehicle_kind_queryset(pair).values_list("pk", flat=True)]
    if ids:
        return ids
    if pair.yard_vehicle_kind_id:
        return [int(pair.yard_vehicle_kind_id)]
    return []


def pair_has_vehicle_kinds(pair: NameSubjectWasteSuffixPair) -> bool:
    return bool(pair_vehicle_kind_ids(pair))


def pair_primary_vehicle_kind(pair: NameSubjectWasteSuffixPair) -> VehicleKindCatalog | None:
    return pair_vehicle_kind_queryset(pair).first() or getattr(pair, "yard_vehicle_kind", None)


def pair_vehicle_kinds_display(pair: NameSubjectWasteSuffixPair, sep: str = ", ") -> str:
    labels = [k.display_label() for k in pair_vehicle_kind_queryset(pair)]
    if labels:
        return sep.join(labels)
    vk = getattr(pair, "yard_vehicle_kind", None)
    return vk.display_label() if vk else ""


def pair_covering_vehicle_kind_ids(pair: NameSubjectWasteSuffixPair) -> list[int]:
    """Sjednocená množina druhů RZ, které směrově pokrývají alespoň jeden druh z řádku F/P."""
    from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task

    out: set[int] = set()
    for task_kind_id in pair_vehicle_kind_ids(pair):
        out |= vehicle_kinds_covering_task(task_kind_id)
    return sorted(out)


def pair_vehicle_kind_constraint_hint(pair: NameSubjectWasteSuffixPair) -> str | None:
    """Proaktivní nápověda, když řádek F/P má jediný druh (slabší vozidlo nelze přiřadit)."""
    task_ids = pair_vehicle_kind_ids(pair)
    if len(task_ids) != 1:
        return None
    kind = VehicleKindCatalog.objects.filter(pk=task_ids[0]).first()
    if not kind:
        return None
    return (
        f"Řádek matice vyžaduje druh {kind.display_label()} — slabší vozidlo z číselníku "
        f"nelze zvolit ani při přeplánování."
    )


def _profile_vehicle_kind_labels(profile) -> str:
    if profile is None:
        return "—"
    labels = [k.display_label() for k in profile.vehicle_kinds.all().order_by("sort_order", "name", "pk")]
    return ", ".join(labels) if labels else "—"


def rz_profile_pair_mismatch_message(
    profile,
    pair: NameSubjectWasteSuffixPair,
    *,
    vehicle_rz_label: str = "—",
) -> str | None:
    """Česká chyba při nekompatibilním RZ vůči druhům na řádku F/P."""
    if rz_profile_serves_pair(profile, pair):
        return None
    pair_label = pair_vehicle_kinds_display(pair) or "vybrané druhy"
    prof_label = _profile_vehicle_kind_labels(profile)
    return (
        f"Vybrané vozidlo {vehicle_rz_label} ({prof_label}) neodpovídá druhu vozidla u páru subjektu "
        f"({pair_label}). Slabší vozidlo nelze přiřadit ani přeplánovat — zvolte silnější RZ "
        f"nebo upravte řádek v číselníku F/P (Povolené odpady a koncovky)."
    )


def pair_hint_vehicle_kind_client_fields(pair: NameSubjectWasteSuffixPair) -> dict:
    """Pole pro JS klienta průvodky (covering kinds + nápověda)."""
    return {
        "yard_vehicle_kind_ids": pair_vehicle_kind_ids(pair),
        "covering_kind_ids": pair_covering_vehicle_kind_ids(pair),
        "vehicle_kind_constraint_hint": pair_vehicle_kind_constraint_hint(pair) or "",
    }


def passport_kind_valid_for_pair(passport_kind_id: int | None, pair: NameSubjectWasteSuffixPair) -> bool:
    """Pasport sedí, pokud jeho druh odpovídá libovolnému druhu z páru (včetně stromu kompatibility)."""
    from catalogs.services.vehicle_kind_compatibility import passport_kind_valid_for_task

    if not passport_kind_id:
        return True
    for task_kind_id in pair_vehicle_kind_ids(pair):
        if passport_kind_valid_for_task(passport_kind_id, task_kind_id):
            return True
    return False


def rz_profile_serves_pair(profile, pair: NameSubjectWasteSuffixPair) -> bool:
    """Profil RZ obslouží alespoň jeden druh vozidla z páru subjektu."""
    from catalogs.services.vehicle_kind_compatibility import rz_profile_serves_task_kind

    if profile is None:
        return False
    for task_kind_id in pair_vehicle_kind_ids(pair):
        if rz_profile_serves_task_kind(profile, task_kind_id):
            return True
    return False


def ordered_kind_ids_for_svoz_task(
    task_vehicle_kind_id: int | None,
    pair: NameSubjectWasteSuffixPair | None,
) -> list[int]:
    """Pořadí zkoušení druhů: nejdřív druh úkolu / plánu, pak ostatní z páru."""
    from_pair = pair_vehicle_kind_ids(pair) if pair else []
    if not from_pair and task_vehicle_kind_id:
        return [int(task_vehicle_kind_id)]
    out: list[int] = []
    if task_vehicle_kind_id:
        tid = int(task_vehicle_kind_id)
        out.append(tid)
    for kid in from_pair:
        if kid not in out:
            out.append(kid)
    return out


def _pair_qs_for_svoz_task(subject_profile_id: int, waste_type_id: int, suffix_id: int):
    return NameSubjectWasteSuffixPair.objects.filter(
        subject_profile_id=subject_profile_id,
        waste_type_id=waste_type_id,
        suffix_id=suffix_id,
    ).prefetch_related("yard_vehicle_kinds", "yard_vehicle_kind")


def pair_for_svoz_task(subject_profile_id: int, waste_type_id: int, suffix_id: int):
    return _pair_qs_for_svoz_task(subject_profile_id, waste_type_id, suffix_id).first()


def pair_for_pruvodka_context(
    *,
    subject_profile=None,
    waste_type_id: int | None = None,
    suffix_id: int | None = None,
    vehicle_rz=None,
    container_passport=None,
    pairs_qs=None,
    preferred_pair_id: int | None = None,
) -> NameSubjectWasteSuffixPair | None:
    """
    Jednoznačný řádek matice pro běžnou jízdu / editaci.

    U stejného odpadu+koncovky může být více řádků (Hák, Řetěz…) — preferovat
    uložený pár, shodu s RZ nebo pasportem kontejneru; ne slepý .first().
    """
    from django.core.exceptions import ObjectDoesNotExist

    if pairs_qs is None:
        if subject_profile is None or not waste_type_id or not suffix_id:
            return None
        pairs_qs = subject_profile.waste_suffix_pairs.filter(
            waste_type_id=int(waste_type_id),
            suffix_id=int(suffix_id),
        ).select_related("yard_vehicle_kind").prefetch_related("yard_vehicle_kinds")

    pairs = list(pairs_qs.order_by("sort_order", "id"))
    if not pairs:
        return None
    if len(pairs) == 1:
        return pairs[0]

    wt_id = int(waste_type_id) if waste_type_id else None
    suf_id = int(suffix_id) if suffix_id else None
    if wt_id is None and pairs:
        wt_id = pairs[0].waste_type_id
    if suf_id is None and pairs:
        suf_id = pairs[0].suffix_id

    prof_rz = None
    if vehicle_rz is not None:
        try:
            prof_rz = vehicle_rz.profile
        except ObjectDoesNotExist:
            prof_rz = None

    passport_kind_id = None
    if container_passport is not None and getattr(container_passport, "vehicle_kind_id", None):
        passport_kind_id = int(container_passport.vehicle_kind_id)

    def _pair_matches_context(pair: NameSubjectWasteSuffixPair) -> bool:
        if wt_id is not None and pair.waste_type_id != wt_id:
            return False
        if suf_id is not None and pair.suffix_id != suf_id:
            return False
        if prof_rz is not None and not rz_profile_serves_pair(prof_rz, pair):
            return False
        if passport_kind_id is not None and not passport_kind_valid_for_pair(passport_kind_id, pair):
            return False
        return True

    if preferred_pair_id:
        preferred = next((p for p in pairs if p.pk == int(preferred_pair_id)), None)
        if preferred is None:
            preferred = (
                NameSubjectWasteSuffixPair.objects.filter(pk=int(preferred_pair_id))
                .select_related("yard_vehicle_kind")
                .prefetch_related("yard_vehicle_kinds")
                .first()
            )
        if preferred and _pair_matches_context(preferred):
            return preferred

    rz_matches = [p for p in pairs if prof_rz is not None and rz_profile_serves_pair(prof_rz, p)]
    if rz_matches:
        return rz_matches[0]

    passport_matches = [
        p for p in pairs if passport_kind_id is not None and passport_kind_valid_for_pair(passport_kind_id, p)
    ]
    if passport_matches:
        return passport_matches[0]

    if any(pair_has_vehicle_kinds(p) for p in pairs):
        return None

    return pairs[0]


def _pair_matches_vehicle_kind_ids(pair: NameSubjectWasteSuffixPair, kind_ids: set[int]) -> bool:
    if not kind_ids:
        return False
    if pair.yard_vehicle_kind_id and int(pair.yard_vehicle_kind_id) in kind_ids:
        return True
    return pair.yard_vehicle_kinds.filter(pk__in=kind_ids).exists()


def _equivalent_vehicle_kind_ids(kind_id: int) -> set[int]:
    from waste_docs.services.svoz_dispatch.vehicle_kind_equivalence import (
        equivalent_vehicle_kind_ids_for_plan_matching,
    )

    return set(equivalent_vehicle_kind_ids_for_plan_matching(int(kind_id))) | {int(kind_id)}


def pair_for_svoz_task_record(task) -> NameSubjectWasteSuffixPair | None:
    """
    Jednoznačný řádek matice pro existující SvozTask.

    U dvora se stejným odpadem/suffixem může být více řádků (Hák, Řetěz…) — vždy
    preferovat řádek, ze kterého požadavek vznikl, nebo shodu s druhem na úkolu
    (včetně ekvivalentních záznamů v číselníku, např. Retez / Řetěz).
    """
    source_pair_id = getattr(task, "source_waste_suffix_pair_id", None)
    if source_pair_id:
        pair = (
            NameSubjectWasteSuffixPair.objects.filter(pk=int(source_pair_id))
            .prefetch_related("yard_vehicle_kinds", "yard_vehicle_kind")
            .first()
        )
        if pair:
            return pair

    qs = _pair_qs_for_svoz_task(
        int(task.subject_profile_id),
        int(task.waste_type_id),
        int(task.suffix_id),
    )
    vk_id = getattr(task, "vehicle_kind_id", None)
    if vk_id:
        vid = int(vk_id)
        match = qs.filter(yard_vehicle_kind_id=vid).first()
        if match:
            return match
        equiv = _equivalent_vehicle_kind_ids(vid)
        for pair in qs.order_by("pk"):
            if _pair_matches_vehicle_kind_ids(pair, equiv):
                return pair
    return qs.first()


def sync_pair_primary_vehicle_kind_fk(pair: NameSubjectWasteSuffixPair) -> None:
    """Zachová staré API: FK = první vybraný druh v M2M."""
    primary = pair_primary_vehicle_kind(pair)
    new_id = primary.pk if primary else None
    if pair.yard_vehicle_kind_id != new_id:
        pair.yard_vehicle_kind_id = new_id
        pair.save(update_fields=["yard_vehicle_kind"])
