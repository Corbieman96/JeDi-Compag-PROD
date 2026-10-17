"""Kdy smí systém generovat instanci ZPO (číslo v šabloně) pro záznam jízdy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from catalogs.models import NameSubjectProfile

from waste_docs.activity_fields import activity_generates_zpo
from waste_docs.zpo_resolved import pair_for_pruvodka

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def system_may_generate_zpo_instance(pruvodka: Pruvodka) -> bool:
    """
    True, pokud činnost povoluje ZPO, pár odpad+koncovka nezakazuje generování
    a profil subjektu má zapnuté systémové ZPO.
    Chybí-li profil subjektu nebo řádek páru v číselníku, chováme se jako dříve u subjektu.
    """
    return explain_system_zpo_generation_block(pruvodka) is None


def explain_system_zpo_generation_block(pruvodka: Pruvodka) -> str | None:
    """None = generování povoleno; jinak krátký důvod blokace."""
    if not activity_generates_zpo(getattr(pruvodka, "activity_id", None)):
        return "u činnosti je vypnuté generování ZPO"
    name_id = getattr(pruvodka, "name_id", None)
    waste_type_id = getattr(pruvodka, "waste_type_id", None)
    suffix_id = getattr(pruvodka, "suffix_id", None)
    if name_id and waste_type_id and suffix_id:
        pair = pair_for_pruvodka(pruvodka)
        if pair is not None and getattr(pair, "suppress_system_zpo", False):
            return "u páru odpad + koncovka je vypnuté systémové generování ZPO"
    if not name_id:
        return None
    prof = (
        NameSubjectProfile.objects.filter(name_id=name_id)
        .select_related("zpo_settings")
        .only("pk", "zpo_settings__system_generates_zpo")
        .first()
    )
    if prof is None:
        return None
    if not bool(getattr(prof.zpo_settings, "system_generates_zpo", True)):
        return "u subjektu je vypnuté systémové generování ZPO"
    return None
