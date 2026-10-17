"""Diagnostika a synchronizace řádku matice (odpad–koncovka) u jízdy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.core.exceptions import ObjectDoesNotExist

from catalogs.models import NameSubjectProfile
from catalogs.services.name_subject_pair_vehicle_kinds import (
    pair_for_pruvodka_context,
    pair_vehicle_kinds_display,
    passport_kind_valid_for_pair,
    rz_profile_serves_pair,
)
from waste_docs.zpo_resolved import pair_for_pruvodka

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def _rz_profile_and_kinds_label(vehicle_rz) -> tuple[Any | None, str]:
    if vehicle_rz is None:
        return None, "—"
    value = (getattr(vehicle_rz, "value", None) or "").strip() or "—"
    try:
        profile = vehicle_rz.profile
    except ObjectDoesNotExist:
        return None, value
    kinds = ", ".join(
        profile.vehicle_kinds.exclude(shortcut="").values_list("shortcut", flat=True).distinct()
    )
    if kinds:
        return profile, f"{value} -> {kinds}"
    return profile, value


def _passport_kind_label(container_passport) -> tuple[int | None, str]:
    if container_passport is None:
        return None, "—"
    number = (getattr(container_passport, "container_number", None) or "").strip()
    prefix = f"#{container_passport.pk}"
    if number:
        prefix = f"{number} ({prefix})"
    kind = getattr(container_passport, "vehicle_kind", None)
    if kind is not None:
        return int(kind.pk), f"{prefix} -> {kind.display_label()}"
    kind_id = getattr(container_passport, "vehicle_kind_id", None)
    if kind_id:
        return int(kind_id), prefix
    return None, prefix


def diagnose_pruvodka_source_pair(item: Pruvodka) -> dict[str, Any]:
    """Stav páru matice u jedné jízdy — uložený FK vs. resolver vs. efektivní."""
    stored_pair_id = getattr(item, "source_waste_suffix_pair_id", None)
    name_id = getattr(item, "name_id", None)
    waste_type_id = getattr(item, "waste_type_id", None)
    suffix_id = getattr(item, "suffix_id", None)

    rz_profile, vehicle_rz_label = _rz_profile_and_kinds_label(getattr(item, "vehicle_rz", None))
    passport_kind_id, passport_kind_label = _passport_kind_label(
        getattr(item, "container_passport", None)
    )

    profile = NameSubjectProfile.objects.filter(name_id=name_id).first() if name_id else None
    candidates: list[dict[str, Any]] = []
    resolved_pair_id: int | None = None
    effective_pair: int | None = None

    if profile and waste_type_id and suffix_id:
        pairs_qs = profile.waste_suffix_pairs.filter(
            waste_type_id=int(waste_type_id),
            suffix_id=int(suffix_id),
        ).select_related("yard_vehicle_kind").prefetch_related("yard_vehicle_kinds")
        pairs = list(pairs_qs.order_by("sort_order", "id"))

        resolved = pair_for_pruvodka_context(
            subject_profile=profile,
            waste_type_id=waste_type_id,
            suffix_id=suffix_id,
            vehicle_rz=getattr(item, "vehicle_rz", None),
            container_passport=getattr(item, "container_passport", None),
            preferred_pair_id=None,
        )
        resolved_pair_id = resolved.pk if resolved else None

        for pair in pairs:
            rz_match = bool(rz_profile is not None and rz_profile_serves_pair(rz_profile, pair))
            passport_match = bool(
                passport_kind_id is not None
                and passport_kind_valid_for_pair(passport_kind_id, pair)
            )
            candidates.append(
                {
                    "pk": pair.pk,
                    "sort_order": pair.sort_order,
                    "vehicle_kinds": pair_vehicle_kinds_display(pair) or "—",
                    "rz_match": rz_match,
                    "passport_match": passport_match,
                    "is_stored": stored_pair_id == pair.pk,
                    "is_resolved": resolved_pair_id == pair.pk,
                }
            )

    if name_id and waste_type_id and suffix_id:
        effective = pair_for_pruvodka(item)
        effective_pair = effective.pk if effective else None

    if not profile or not waste_type_id or not suffix_id:
        status = "no_matrix_input"
        message = "Chybí subjekt, odpad nebo koncovka — nelze určit řádek matice."
    elif not candidates:
        status = "no_candidates"
        message = "U subjektu není žádný řádek pro zvolený odpad a koncovku."
    elif resolved_pair_id is None:
        status = "unresolvable"
        message = (
            "Žádný řádek matice neodpovídá RZ ani pasportu kontejneru "
            "(u řádků jsou nastavené druhy vozidel)."
        )
    elif stored_pair_id is None:
        status = "missing_stored"
        message = f"FK není uložený; resolver doporučuje řádek pk {resolved_pair_id}."
    elif int(stored_pair_id) != int(resolved_pair_id):
        status = "mismatch"
        message = (
            f"Uložený řádek pk {stored_pair_id} neodpovídá resolveru pk {resolved_pair_id}."
        )
    else:
        status = "ok"
        message = f"Uložený řádek pk {stored_pair_id} odpovídá resolveru."

    return {
        "pruvodka_pk": item.pk,
        "stored_pair_id": stored_pair_id,
        "resolved_pair_id": resolved_pair_id,
        "effective_pair_id": effective_pair,
        "status": status,
        "message": message,
        "candidates": candidates,
        "vehicle_rz_label": vehicle_rz_label,
        "passport_kind_label": passport_kind_label,
        "passport_kind_id": passport_kind_id,
    }


def sync_pruvodka_source_pair(item: Pruvodka, *, force: bool = False) -> bool:
    """
    Zapíše source_waste_suffix_pair podle resolveru (RZ + pasport).

    Vrátí True, pokud došlo k zápisu do DB.
    """
    diag = diagnose_pruvodka_source_pair(item)
    resolved_pair_id = diag.get("resolved_pair_id")
    if resolved_pair_id is None:
        return False

    status = diag.get("status")
    stored_pair_id = diag.get("stored_pair_id")
    if not force and status not in ("missing_stored", "mismatch"):
        return False
    if stored_pair_id == resolved_pair_id:
        return False

    from waste_docs.models import Pruvodka

    Pruvodka.objects.filter(pk=item.pk).update(source_waste_suffix_pair_id=int(resolved_pair_id))
    item.source_waste_suffix_pair_id = int(resolved_pair_id)
    return True
