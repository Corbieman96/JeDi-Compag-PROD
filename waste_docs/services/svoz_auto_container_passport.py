"""Po úspěšné auto-průvodce ze svozu doplnit FK na číselník Pasport kontejnerů (nebo jej založit)."""

from __future__ import annotations

from django.db import IntegrityError, transaction

from catalogs.models import ContainerPassport
from catalogs.services.vehicle_kind_compatibility import vehicle_kind_covers_task

from waste_docs.services.container_passport_ride_validation import passport_by_container_number

_CONTAINER_NUMBER_MAXLEN = ContainerPassport._meta.get_field("container_number").max_length
_STUB_NOTES = (
    "Zřízeno automaticky ze svozu sběrného dvora — doplňte detaily pasportu v Číselníky → Pasport kontejnerů."
)


def _primary_container_fragment(raw: str) -> str:
    text = (raw or "").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return parts[0] if parts else ""


def ensure_container_passport_for_svoz(
    container_number: str,
    *,
    vehicle_kind_id: int | None = None,
    vehicle_kind_ids: list[int] | None = None,
) -> ContainerPassport | None:
    """
    Vrátí pasport pro číslo kontejneru; zkusí všechny druhy vozidla ze seznamu (sběrný dvůr).

    Pokud pasport existuje, musí být kompatibilní s alespoň jedním zkoušeným druhem.
  """
    num_raw = (container_number or "").strip()
    kind_ids = list(vehicle_kind_ids or [])
    if vehicle_kind_id and int(vehicle_kind_id) not in kind_ids:
        kind_ids.insert(0, int(vehicle_kind_id))
    if not num_raw or not kind_ids:
        return None

    num_passport_store = num_raw[:_CONTAINER_NUMBER_MAXLEN]
    existing = passport_by_container_number(num_raw)
    if existing:
        for kid in kind_ids:
            if vehicle_kind_covers_task(int(kid), int(existing.vehicle_kind_id)):
                return existing
        return None

    for kid in kind_ids:
        try:
            return ContainerPassport.objects.create(
                container_number=num_passport_store,
                vehicle_kind_id=int(kid),
                color="—",
                notes=_STUB_NOTES,
            )
        except IntegrityError:
            again = passport_by_container_number(num_raw)
            if again and vehicle_kind_covers_task(int(kid), int(again.vehicle_kind_id)):
                return again
    return None


def sync_container_passport_after_svoz_auto_pruvodka(
    pruvodka_id: int,
    *,
    vehicle_kind_id: int | None,
    fallback_container_numbers: str = "",
) -> None:
    """
    Pokud je známé číslo kontejneru (z průvodky nebo přímo ze zadání dvora při aktivitě bez pole kontejneru)
    a druh vozidla ze svozu, váže řádek `ContainerPassport`; při potřebě doplní stub v číselníku.

    Nepřepíše již nastavený `container_passport` u průvodky.
    """
    if not vehicle_kind_id or not pruvodka_id:
        return

    from waste_docs.models import Pruvodka

    pr_field = Pruvodka._meta.get_field("container_number")
    _pr_uvodka_cn_max = pr_field.max_length

    with transaction.atomic():
        locked = (
            Pruvodka.objects.select_for_update()
            .filter(pk=pruvodka_id, container_passport_id__isnull=True)
            .first()
        )
        if not locked:
            return

        num_raw = (locked.container_number or "").strip()
        if not num_raw:
            num_raw = _primary_container_fragment(fallback_container_numbers).strip()
        if not num_raw:
            return

        passport = ensure_container_passport_for_svoz(num_raw, vehicle_kind_id=vehicle_kind_id)
        if not passport:
            return

        num_pruvodka_store = num_raw[:_pr_uvodka_cn_max]
        locked.container_passport_id = passport.pk
        update_fields = ["container_passport_id"]
        if not (locked.container_number or "").strip():
            locked.container_number = num_pruvodka_store
            update_fields.append("container_number")
        locked.save(update_fields=update_fields)


__all__ = [
    "ensure_container_passport_for_svoz",
    "sync_container_passport_after_svoz_auto_pruvodka",
]
