"""Dotazy na párování dokumentů (ZPO / suffix) pro průvodku — sdílené mezi views a servisy."""

from waste_docs.models import Pruvodka
from waste_docs.zpo_resolved import pair_for_pruvodka


def pair_docs_for_pruvodka(item: Pruvodka):
    if not (item.name_id and item.waste_type_id and item.suffix_id):
        return None
    return pair_for_pruvodka(item)
