"""Diagnostika chybějící instance ZPO u průvodky."""

from __future__ import annotations

from django.core.files.storage import default_storage

from waste_docs.services.pruvodka_pair_docs import pair_docs_for_pruvodka
from waste_docs.zpo_policy import explain_system_zpo_generation_block
from waste_docs.zpo_resolved import display_zpo_file_for_pruvodka, effective_zpo_file, pair_for_name_waste_suffix

if False:  # TYPE_CHECKING
    from waste_docs.models import Pruvodka

_last_ensure_failures: dict[int, str] = {}


def record_zpo_ensure_failure(pk: int, reason: str) -> None:
    text = (reason or "").strip()
    if text:
        _last_ensure_failures[int(pk)] = text


def clear_zpo_ensure_failure(pk: int) -> None:
    _last_ensure_failures.pop(int(pk), None)


def last_zpo_ensure_failure(pk: int) -> str:
    return (_last_ensure_failures.get(int(pk)) or "").strip()


def zpo_instance_is_ready(item) -> bool:
    return display_zpo_file_for_pruvodka(item) is not None


def explain_missing_zpo_instance(item, *, pair=None) -> str | None:
    """
    Lidsky čitelný důvod, proč není k dispozici vygenerované ZPO s číslem listu.
    None = instance je v pořádku, nebo se u jízdy nečeká.
    """
    if zpo_instance_is_ready(item):
        return None

    snd = (item.snd_cislo_listu or "").strip()
    if not snd:
        return None

    if not (item.name_id and item.waste_type_id and item.suffix_id):
        return "chybí subjekt, druh odpadu nebo koncovku"

    block = explain_system_zpo_generation_block(item)
    if block:
        return block

    if pair is None:
        pair = pair_docs_for_pruvodka(item)
    if pair is None:
        pair = pair_for_name_waste_suffix(item.name_id, item.waste_type_id, item.suffix_id)
    if pair is None:
        return "v číselníku není pár subjekt + odpad + koncovka"

    template = effective_zpo_file(pair)
    if not template:
        return "k páru není přiřazen vzor ZPO v knihovně"

    template_name = (getattr(template, "name", None) or "").strip()
    if template_name and not default_storage.exists(template_name):
        return "soubor vzoru ZPO na disku chybí"

    instance_name = ""
    if item.zpo_instance_file and getattr(item.zpo_instance_file, "name", None):
        instance_name = item.zpo_instance_file.name.strip()
    if instance_name and not default_storage.exists(instance_name):
        return "záznam vygenerovaného ZPO v databázi existuje, ale soubor na disku chybí"

    failure = last_zpo_ensure_failure(item.pk or 0)
    if failure:
        return f"generování selhalo: {failure}"

    return "generování ZPO se nepodařilo dokončit (zkuste Náhled / vygenerovat ZPO)"


def zpo_template_url_for_pruvodka(item, *, pair=None) -> str:
    """URL vzoru ZPO z knihovny (náhled bez čísla listu), pokud existuje."""
    if pair is None:
        pair = pair_docs_for_pruvodka(item)
    template = effective_zpo_file(pair)
    if not template:
        return ""
    name = (getattr(template, "name", None) or "").strip()
    if name and not default_storage.exists(name):
        return ""
    return (getattr(template, "url", None) or "").strip()
