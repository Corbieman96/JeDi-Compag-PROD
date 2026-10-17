"""Určení skutečného souboru ZPO u páru subjekt–odpad–koncovka (knihovna ZpoDocument)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from catalogs.models import NameSubjectWasteSuffixPair

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def pair_for_name_waste_suffix(
    name_id: int,
    waste_type_id: int,
    suffix_id: int,
) -> NameSubjectWasteSuffixPair | None:
    pairs = list(
        NameSubjectWasteSuffixPair.objects.select_related(
            "zpo",
            "subject_profile",
            "waste_type",
            "suffix",
        )
        .filter(
            subject_profile__name_id=name_id,
            waste_type_id=waste_type_id,
            suffix_id=suffix_id,
        )
        .order_by("sort_order", "id")
    )
    if not pairs:
        return None
    for pair in pairs:
        if effective_zpo_file(pair):
            return pair
    return pairs[0]


def pair_for_pruvodka(item: Pruvodka) -> NameSubjectWasteSuffixPair | None:
    """Konkrétní řádek matice pro jízdu — uložený FK nebo resolver podle RZ/pasportu."""
    from catalogs.models import NameSubjectProfile
    from catalogs.services.name_subject_pair_vehicle_kinds import pair_for_pruvodka_context

    stored_id = getattr(item, "source_waste_suffix_pair_id", None)
    if stored_id:
        pair = (
            NameSubjectWasteSuffixPair.objects.filter(pk=int(stored_id))
            .select_related("zpo", "subject_profile", "waste_type", "suffix")
            .first()
        )
        if pair:
            return pair

    name_id = getattr(item, "name_id", None)
    waste_type_id = getattr(item, "waste_type_id", None)
    suffix_id = getattr(item, "suffix_id", None)
    if not (name_id and waste_type_id and suffix_id):
        return None

    profile = NameSubjectProfile.objects.filter(name_id=name_id).first()
    if not profile:
        return None

    return pair_for_pruvodka_context(
        subject_profile=profile,
        waste_type_id=waste_type_id,
        suffix_id=suffix_id,
        vehicle_rz=getattr(item, "vehicle_rz", None),
        container_passport=getattr(item, "container_passport", None),
        preferred_pair_id=stored_id,
    )


def effective_zpo_file(pair: NameSubjectWasteSuffixPair | None):
    """Soubor ZPO z knihovny (FK ``pair.zpo``)."""
    if not pair or not pair.zpo_id:
        return None
    zpo = pair.zpo
    if zpo and zpo.file and getattr(zpo.file, "name", None):
        return zpo.file
    return None


def zpo_kind_for_file(file_obj) -> str:
    name = (file_obj.name or "").lower() if file_obj else ""
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        return "xlsx"
    if name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg"):
        return "image"
    return "other"


def display_zpo_file_for_pruvodka(item, pair=None):
    """
    Soubor ZPO zobrazený u konkrétní průvodky: vygenerovaná instance.
    Holý vzor z číselníku se vrátí jen pokud průvodka nemá snd_cislo_listu
    (jinak by se tisklo nečíslované ZPO místo instance).
    """
    from django.core.files.storage import default_storage

    from waste_docs.models import Pruvodka

    if not isinstance(item, Pruvodka):
        return None
    instance_name = ""
    if item.zpo_instance_file and getattr(item.zpo_instance_file, "name", None):
        instance_name = item.zpo_instance_file.name
        if default_storage.exists(instance_name):
            return item.zpo_instance_file
    snd = (item.snd_cislo_listu or "").strip()
    if snd:
        return None
    if pair is None:
        if not (item.name_id and item.waste_type_id and item.suffix_id):
            return None
        pair = pair_for_pruvodka(item)
    return effective_zpo_file(pair)
