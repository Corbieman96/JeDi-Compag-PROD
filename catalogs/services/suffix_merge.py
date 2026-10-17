"""Sloučení dvou řádků SuffixCatalog (např. překlep vs oprava)."""

from __future__ import annotations

from django.apps import apps
from django.db import transaction

from catalogs.models import (
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    SuffixSiteProfile,
    ZpoDocument,
)
from catalogs.services.subject_disposal import sync_subject_allowed_from_pairs


def _merge_suffix_site_profile_into(*, keep: SuffixSiteProfile, discard: SuffixSiteProfile) -> None:
    """
    Sloučí ``discard`` do ``keep``: sjednotí M2M odpadů, doplní prázdná pole na cíli ze zdroje.
    Nakonec smaže ``discard``.
    """
    for wt in discard.accepted_waste_types.all():
        keep.accepted_waste_types.add(wt)
    for wt in discard.produced_waste_types.all():
        keep.produced_waste_types.add(wt)

    if not (keep.name or "").strip() and (discard.name or "").strip():
        keep.name = discard.name
    if keep.ico_id is None and discard.ico_id is not None:
        keep.ico_id = discard.ico_id
    if not (keep.icz or "").strip() and (discard.icz or "").strip():
        keep.icz = discard.icz
    if not (keep.facility_type or "").strip() and (discard.facility_type or "").strip():
        keep.facility_type = discard.facility_type
    if keep.address_id is None and discard.address_id is not None:
        keep.address_id = discard.address_id
    if not (keep.zuj or "").strip() and (discard.zuj or "").strip():
        keep.zuj = discard.zuj
    if keep.latitude is None and discard.latitude is not None:
        keep.latitude = discard.latitude
    if keep.longitude is None and discard.longitude is not None:
        keep.longitude = discard.longitude

    keep.save()
    discard.delete()


def merge_suffix_catalog_rows(*, source_pk: int, target_pk: int) -> dict:
    """
    Přesune všechny vazby z ``source_pk`` na ``target_pk`` a smaže zdrojový řádek.

    U párů odpad–koncovka: pokud už existuje jiný pár se stejným subjektem, druhem odpadu
    a ``target_pk``, zdrojový pár se smaže (duplicita po sloučení).

    Pokud existují ``SuffixSiteProfile`` na zdroji i na cíli, profily se sloučí do cílového
    (M2M odpadů, doplnění prázdných polí).

    Vrací slovník s počty provedených operací.
    """
    if source_pk == target_pk:
        raise ValueError("source_pk a target_pk musí být různé.")

    source = SuffixCatalog.objects.get(pk=source_pk)
    target = SuffixCatalog.objects.get(pk=target_pk)
    source_value_saved = source.value
    target_value_saved = target.value

    stats: dict[str, int | str] = {
        "pairs_updated": 0,
        "pairs_deleted_duplicate": 0,
        "zpo_documents_updated": 0,
        "pruvodka_updated": 0,
        "m2m_swapped": 0,
        "site_profiles_moved": 0,
        "site_profiles_merged": 0,
    }
    profiles_to_sync: set[int] = set()

    Pruvodka = apps.get_model("waste_docs", "Pruvodka")

    with transaction.atomic():
        for pair in NameSubjectWasteSuffixPair.objects.filter(suffix_id=source_pk).select_related("subject_profile"):
            sp_id = pair.subject_profile_id
            wt_id = pair.waste_type_id
            duplicate = (
                NameSubjectWasteSuffixPair.objects.filter(
                    subject_profile_id=sp_id,
                    waste_type_id=wt_id,
                    suffix_id=target_pk,
                )
                .exclude(pk=pair.pk)
                .first()
            )
            if duplicate:
                pair.delete()
                stats["pairs_deleted_duplicate"] += 1
            else:
                pair.suffix_id = target_pk
                pair.save(update_fields=["suffix_id"])
                stats["pairs_updated"] += 1
            profiles_to_sync.add(sp_id)

        stats["zpo_documents_updated"] = ZpoDocument.objects.filter(suffix_id=source_pk).update(suffix_id=target_pk)

        stats["pruvodka_updated"] = Pruvodka.objects.filter(suffix_id=source_pk).update(suffix_id=target_pk)

        site_src = SuffixSiteProfile.objects.filter(suffix_id=source_pk).first()
        site_tgt = SuffixSiteProfile.objects.filter(suffix_id=target_pk).first()

        if site_src and site_tgt:
            _merge_suffix_site_profile_into(keep=site_tgt, discard=site_src)
            stats["site_profiles_merged"] = 1
        elif site_src and not site_tgt:
            site_src.suffix_id = target_pk
            site_src.save(update_fields=["suffix_id"])
            stats["site_profiles_moved"] = 1

        Through = NameSubjectProfile.allowed_suffixes.through
        for row in Through.objects.filter(suffixcatalog_id=source_pk).select_related("namesubjectprofile"):
            prof: NameSubjectProfile = row.namesubjectprofile
            prof.allowed_suffixes.remove(source)
            if not prof.allowed_suffixes.filter(pk=target_pk).exists():
                prof.allowed_suffixes.add(target)
            stats["m2m_swapped"] += 1

        source.delete()

    for pid in profiles_to_sync:
        sync_subject_allowed_from_pairs(NameSubjectProfile.objects.get(pk=pid))

    stats["source_value"] = source_value_saved
    stats["target_value"] = target_value_saved
    return stats
