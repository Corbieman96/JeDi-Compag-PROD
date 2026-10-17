"""Řidiči a RZ vozidel pro plán svozů (druh vozidla z řádku matice)."""

from __future__ import annotations

from collections import defaultdict

from django.db.models import Q

from catalogs.models import DriverProfile, VehicleRzCatalog, VehicleRzProfile
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.plan import PlanSlot
from waste_docs.services.svoz_dispatch.plan_coverage import _row_kind_value


def driver_queryset_for_vehicle_kind(vehicle_kind_id: int):
    """Řidič má druh vozidla v M2M nebo u přiřazeného profilu RZ (včetně kompatibilních druhů ze stromu)."""
    from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task

    kind_ids = list(vehicle_kinds_covering_task(int(vehicle_kind_id)))
    return (
        DriverProfile.objects.filter(
            Q(allowed_vehicle_kinds__id__in=kind_ids)
            | Q(allowed_vehicle_rz__vehicle_kinds__id__in=kind_ids)
        )
        .distinct()
        .order_by("last_name", "first_name", "personal_number")
    )


def vehicle_rz_queryset_for_vehicle_kind(vehicle_kind_id: int):
    """RZ jejichž profil má daný druh vozidla nebo kompatibilní druh ze stromu / M2M."""
    from catalogs.services.vehicle_kind_compatibility import vehicle_kinds_covering_task

    kind_ids = list(vehicle_kinds_covering_task(int(vehicle_kind_id)))
    return (
        VehicleRzCatalog.objects.filter(profile__vehicle_kinds__id__in=kind_ids)
        .select_related("profile")
        .distinct()
        .order_by("value")
    )


def drivers_for_dispatch_plan_kind_section(
    vehicle_kind_id: int,
    assigned_driver_ids: list[int | None],
    *,
    eligible_drivers: list[DriverProfile] | None = None,
) -> list[DriverProfile]:
    """
    Řidiči do comboboxu řádku plánu: způsobilí pro druh vozidla + již přiřazení,
    kteří způsobilí nejsou (zobrazí se do opravy profilu / výměny).

    `eligible_drivers` — volitelně předaný seznam (stejný druh u více dvorů → jeden dotaz).
    """
    if eligible_drivers is not None:
        eligible = list(eligible_drivers)
    else:
        eligible = list(driver_queryset_for_vehicle_kind(vehicle_kind_id))
    eligible_ids = {d.pk for d in eligible}
    assigned = {i for i in assigned_driver_ids if i}
    missing = assigned - eligible_ids
    if not missing:
        return eligible
    out: list[DriverProfile] = list(eligible)
    seen = set(eligible_ids)
    for d in DriverProfile.objects.filter(pk__in=missing).order_by(
        "last_name", "first_name", "personal_number"
    ):
        if d.pk not in seen:
            seen.add(d.pk)
            out.append(d)
    return out


def vehicle_rzs_for_dispatch_plan_section(
    vehicle_kind_id: int,
    assigned_rz_ids: list[int | None],
    *,
    eligible_rzs: list[VehicleRzCatalog] | None = None,
) -> list[VehicleRzCatalog]:
    """RZ do comboboxu + již uložená mimo nabídku."""
    if eligible_rzs is not None:
        eligible = list(eligible_rzs)
    else:
        eligible = list(vehicle_rz_queryset_for_vehicle_kind(vehicle_kind_id))
    eligible_ids = {z.pk for z in eligible}
    assigned = {i for i in assigned_rz_ids if i}
    missing = assigned - eligible_ids
    if not missing:
        return eligible
    out: list[VehicleRzCatalog] = list(eligible)
    seen = set(eligible_ids)
    for rz in VehicleRzCatalog.objects.filter(pk__in=missing).select_related("profile").order_by("value"):
        if rz.pk not in seen:
            seen.add(rz.pk)
            out.append(rz)
    return out


def rz_valid_for_vehicle_kind(rz_id: int, vehicle_kind_id: int) -> bool:
    from catalogs.services.vehicle_kind_compatibility import rz_profile_serves_task_kind

    prof = (
        VehicleRzProfile.objects.filter(rz_id=rz_id)
        .prefetch_related("vehicle_kinds")
        .first()
    )
    if not prof:
        return False
    return rz_profile_serves_task_kind(prof, int(vehicle_kind_id))


def _driver_may_use_rz(driver_id: int, rz_id: int) -> bool:
    d = DriverProfile.objects.prefetch_related("allowed_vehicle_rz").filter(pk=driver_id).first()
    if not d:
        return False
    profs = list(d.allowed_vehicle_rz.all())
    if not profs:
        return True
    return any(p.rz_id == rz_id for p in profs)


def existing_plan_slot_pairs_by_cell(
    plan_date,
    yard_ids: list[int],
) -> dict[tuple[int, int, str], set[tuple[int, int | None]]]:
    """(subjekt, vehicle_kind_id, row_kind) -> množina (driver_id, vehicle_rz_id) z aktuálního plánu."""
    out: dict[tuple[int, int, str], set[tuple[int, int | None]]] = defaultdict(set)
    for r in SvozYardDriverPlan.objects.filter(
        plan_date=plan_date,
        subject_profile_id__in=yard_ids,
    ).values("subject_profile_id", "vehicle_kind_id", "row_kind", "driver_id", "vehicle_rz_id"):
        rk = _row_kind_value(r["row_kind"])
        out[(r["subject_profile_id"], r["vehicle_kind_id"], rk)].add(
            (r["driver_id"], r["vehicle_rz_id"])
        )
    return out


def validate_plan_drivers_for_vehicle_kinds(
    *,
    plan_date,
    yard_ids: list[int],
    standard_rows: list[tuple[int, int, list[PlanSlot]]],
    exception_rows: list[tuple[int, int, list[PlanSlot]]],
) -> str | None:
    """
    Vrátí chybovou hlášku při neplatném řidiči / RZ (nové přiřazení).
    Ponechání stávajícího řidiče nebo dvojice (řidič, RZ) z uloženého plánu je OK.
    """
    existing_pairs = existing_plan_slot_pairs_by_cell(plan_date, yard_ids)
    elig_cache: dict[int, set[int]] = {}

    def elig_ids(vk: int) -> set[int]:
        if vk not in elig_cache:
            elig_cache[vk] = set(
                driver_queryset_for_vehicle_kind(vk).values_list("pk", flat=True)
            )
        return elig_cache[vk]

    def check(row_kind, rows: list[tuple[int, int, list[PlanSlot]]]) -> str | None:
        rk = _row_kind_value(row_kind)
        for subj_id, vk_id, slots in rows:
            prev_pairs = existing_pairs.get((subj_id, vk_id, rk), set())
            prev_drivers = {d for d, _ in prev_pairs}
            elig = elig_ids(vk_id)
            for slot in slots:
                did, rz_id = slot[0], slot[1]
                if not did:
                    continue
                if not rz_id:
                    return (
                        "Uložení se nepodařilo: u vybraného řidiče musíte vybrat také RZ vozidla."
                    )
                if did not in elig and did not in prev_drivers:
                    return (
                        "Uložení se nepodařilo: vybraný řidič nemá v číselníku povolený tento druh vozidla "
                        "(doplňte „Druhy vozidel, které může řídit“ nebo profil RZ)."
                    )
                if not rz_valid_for_vehicle_kind(rz_id, vk_id):
                    return (
                        "Uložení se nepodařilo: vybrané RZ vozidla neodpovídá druhu vozidla u řádku plánu."
                    )
                # V plánu svozů neblokujeme uložení na vazbě řidič->konkrétní RZ.
                # Stačí validace druhu vozidla; konkrétní RZ je dispečerské rozhodnutí dne.
        return None

    err = check(SvozYardDriverPlan.RowKind.STANDARD, standard_rows)
    if err:
        return err
    return check(SvozYardDriverPlan.RowKind.EXCEPTION, exception_rows)
