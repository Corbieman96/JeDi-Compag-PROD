from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q

from catalogs.models import VehicleKindCatalog
from catalogs.services.vehicle_kind_compatibility import compatible_kind_ids
from waste_docs.models import Pruvodka, RideTemplate


def expanded_vehicle_kind_ids_for_template_filter(raw_ids: list[int]) -> list[int]:
    """Rozšíří druhy vozidla o kompatibilní (strom + M2M) pro filtr šablon jízd."""
    out: set[int] = set()
    for kid in raw_ids:
        if kid:
            out |= compatible_kind_ids(int(kid))
    return list(out)


def filter_ride_templates_by_vehicle_kind_ids(qs, kind_ids: list[int]):
    """Šablony pro dané druhy vozidla včetně kompatibilních (např. H ↔ 3H)."""
    expanded = expanded_vehicle_kind_ids_for_template_filter(kind_ids)
    if not expanded:
        return qs.none()
    return qs.filter(
        Q(vehicle_kind_id__in=expanded) | Q(applicable_vehicle_kinds__id__in=expanded)
    ).distinct()


def ride_templates_visible_queryset(user: AbstractBaseUser):
    """Šablony v seznamu / JSON: dispečer a admin vidí všechny, ostatní jen vlastní."""
    from users.services.access import can_see_all_waste_docs

    if not user.is_authenticated:
        return RideTemplate.objects.none()
    if can_see_all_waste_docs(user):
        return RideTemplate.objects.all()
    return RideTemplate.objects.filter(created_by=user)


def preview_vehicle_kinds_for_template_from_pruvodka(item: Pruvodka) -> list[VehicleKindCatalog]:
    """Druhy vozidel nabízené při vytvoření šablony z detailu jízdy (stejná logika jako při uložení)."""
    return _candidate_vehicle_kinds_for_pruvodka(item)


def _candidate_vehicle_kinds_for_pruvodka(item: Pruvodka) -> list[VehicleKindCatalog]:
    if not item.vehicle_rz_id:
        raise ValueError("Jízda nemá vybranou RZ vozidla.")
    profile = getattr(item.vehicle_rz, "profile", None)
    if not profile:
        raise ValueError("Vybraná RZ nemá profil vozidla.")
    kinds = list(profile.vehicle_kinds.order_by("sort_order", "name"))
    if not kinds:
        raise ValueError("Vybraná RZ nemá přiřazený žádný druh vozidla.")
    if item.activity_id:
        activity_kind_ids = set(item.activity.vehicle_kinds.values_list("id", flat=True))
        if activity_kind_ids:
            matched = [k for k in kinds if k.id in activity_kind_ids]
            kinds = matched if matched else kinds
    if item.driver_id:
        driver_kind_ids = set(item.driver.allowed_vehicle_kinds.values_list("id", flat=True))
        if driver_kind_ids:
            matched = [k for k in kinds if k.id in driver_kind_ids]
            kinds = matched if matched else kinds
    if not kinds:
        raise ValueError("Nelze určit druhy vozidla pro šablonu (zkontrolujte činnost, RZ a řidiče).")
    return kinds


def build_ride_template_title(item: Pruvodka) -> str:
    base = " / ".join(
        part
        for part in [
            (item.activity_snapshot or "").strip(),
            (item.waste_type_snapshot or "").strip(),
            (item.suffix_snapshot or "").strip(),
        ]
        if part
    )
    return base or f"Šablona z jízdy #{item.pk}"


def create_ride_template_from_pruvodka(
    *, item: Pruvodka, created_by, title: str = "", vehicle_kind_ids: list[int]
) -> RideTemplate:
    candidates = _candidate_vehicle_kinds_for_pruvodka(item)
    allowed_ids = {k.pk for k in candidates}
    try:
        chosen_ids = {int(x) for x in vehicle_kind_ids}
    except (TypeError, ValueError) as exc:
        raise ValueError("Neplatný výběr druhů vozidla.") from exc
    if not chosen_ids:
        raise ValueError("Vyberte alespoň jeden druh vozidla pro šablonu.")
    if not chosen_ids <= allowed_ids:
        raise ValueError("Vyberte jen druhy vozidel, které odpovídají této jízdě (RZ, činnost, řidič).")
    kind_objs = list(
        VehicleKindCatalog.objects.filter(pk__in=chosen_ids).order_by("sort_order", "name", "pk")
    )
    if not kind_objs:
        raise ValueError("Vyberte alespoň jeden druh vozidla pro šablonu.")
    primary = kind_objs[0]
    final_title = (title or "").strip() or build_ride_template_title(item)
    tpl = RideTemplate.objects.create(
        title=final_title,
        activity=item.activity,
        vehicle_kind=primary,
        name=item.name,
        ico=item.ico,
        address=item.address,
        waste_type=item.waste_type,
        suffix=item.suffix,
        vehicle_rz=item.vehicle_rz,
        driver=item.driver,
        container_number=item.container_number,
        container_number_2=item.container_number_2,
        contact_phone=item.contact_phone,
        contract_number=item.contract_number,
        contact_note=item.contact_note,
        created_by=created_by,
    )
    tpl.applicable_vehicle_kinds.set([k.pk for k in kind_objs])
    return tpl
