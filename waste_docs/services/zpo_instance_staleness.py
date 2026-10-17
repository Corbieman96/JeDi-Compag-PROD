"""Kdy je instance ZPO u průvodky zastaralá a je třeba ji přegenerovat."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.files.storage import default_storage

from waste_docs.zpo_policy import system_may_generate_zpo_instance
from waste_docs.zpo_resolved import effective_zpo_file, pair_for_pruvodka

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def zpo_instance_needs_regeneration(item: Pruvodka, *, pair=None, force: bool = False) -> bool:
    """
    True pokud chybí instance ZPO nebo je zastaralá (SND, revize generátoru, soubor na disku).
    force=True vždy vrátí True (explicitní přegenerování po úpravě průvodky).
    """
    if force:
        return True
    if not system_may_generate_zpo_instance(item):
        return False
    if not (item.snd_cislo_listu or "").strip():
        return False
    if pair is None:
        pair = pair_for_pruvodka(item) if (item.name_id and item.waste_type_id and item.suffix_id) else None
    if not effective_zpo_file(pair):
        return False

    instance_name = ""
    if item.zpo_instance_file and getattr(item.zpo_instance_file, "name", None):
        instance_name = item.zpo_instance_file.name
    if not instance_name or not default_storage.exists(instance_name):
        return True
    if (item.zpo_instance_for_snd or "") != (item.snd_cislo_listu or ""):
        return True
    from waste_docs.zpo_instance_generator import CURRENT_ZPO_GENERATOR_REVISION

    if (getattr(item, "zpo_generator_revision", 0) or 0) < CURRENT_ZPO_GENERATOR_REVISION:
        return True
    return False
