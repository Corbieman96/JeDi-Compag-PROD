"""Stav jízdy po uložení záznamu vs. po vygenerování průvodky (Excel)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def apply_pruvodka_status_after_save(instance: Pruvodka) -> None:
    """
    Vygenerováno = existuje soubor průvodky (Excel); jinak Založeno.
    Volat na objektu před save() po vyplnění polí formuláře.
    """
    from waste_docs.models import Pruvodka

    name = getattr(instance.generated_file, "name", None) if instance.generated_file else None
    if name:
        instance.status = Pruvodka.Status.GENERATED
    else:
        instance.status = Pruvodka.Status.RECORDED
