"""Ukládání denního plánu řidičů (a RZ vozidel) u sběrných dvorů."""

from __future__ import annotations

from collections import defaultdict

from django.db import transaction

from waste_docs.models import SvozYardDriverPlan

# (driver_id, vehicle_rz_id | None, poznámka k RZ, váha) — jeden slot v pořadí round-robinu
PlanSlot = tuple[int, int | None, str, int]


def validate_plan_driver_uniqueness(
    *,
    standard_rows: list[tuple[int, int, list[PlanSlot]]],
    exception_pair_slots: list[tuple[int, int, int, PlanSlot | tuple[int, int | None, str]]],
) -> str | None:
    """
    Kontrola konfliktů před uložením plánu.
    Vrátí chybovou hlášku, pokud by uložení porušilo pravidla slotů.
    """
    for _subj_id, _vk_id, slots in standard_rows:
        seen: set[int] = set()
        for slot in slots:
            driver_id = slot[0]
            if not driver_id:
                continue
            if driver_id in seen:
                return (
                    "Uložení se nepodařilo: u běžného svozu je stejný řidič vybrán ve více "
                    "slotech — každého řidiče zadejte jen jednou."
                )
            seen.add(driver_id)

    exc_by_slot: dict[tuple[int, int, int], int] = {}
    for subj_id, vk_id, sort_order, slot in exception_pair_slots:
        driver_id = slot[0]
        if not driver_id:
            continue
        cell = (subj_id, vk_id, int(sort_order))
        if cell in exc_by_slot and exc_by_slot[cell] != driver_id:
            return (
                "Uložení se nepodařilo: u výjimek matice je ke stejnému slotu V "
                "přiřazeno více různých řidičů — sjednoťte přiřazení v řádcích matice."
            )
        exc_by_slot[cell] = driver_id
    return None


def replace_yard_driver_plan_for_date(
    *,
    plan_date,
    standard_rows: list[tuple[int, int, list[PlanSlot]]],
    exception_rows: list[tuple[int, int, list[PlanSlot]]] | None = None,
    exception_pair_slots: list[tuple[int, int, int, PlanSlot]] | None = None,
) -> None:
    """
    Nahradí všechny záznamy plánu pro `plan_date`.

    `standard_rows`: běžný svoz — `(subject_profile_id, vehicle_kind_id, sloty B1–B4)`.
    `exception_pair_slots`: výjimky podle řádku matice —
    `(subject_profile_id, vehicle_kind_id, sort_order 0–3, (driver_id, rz_id, note))`.
    `exception_rows`: zpětná kompatibilita (starý formát V-slots po druhu vozidla).
    """
    with transaction.atomic():
        SvozYardDriverPlan.objects.filter(plan_date=plan_date).delete()
        bulk = []

        def _append(subject_id: int, vehicle_kind_id: int, slots: list[PlanSlot], row_kind: str) -> None:
            seen: set[int] = set()
            order = 0
            for slot in slots:
                driver_id, rz_id, note = slot[0], slot[1], slot[2]
                weight = slot[3] if len(slot) > 3 else 1
                if not driver_id or driver_id in seen:
                    continue
                seen.add(driver_id)
                bulk.append(
                    SvozYardDriverPlan(
                        plan_date=plan_date,
                        subject_profile_id=subject_id,
                        vehicle_kind_id=vehicle_kind_id,
                        driver_id=driver_id,
                        vehicle_rz_id=rz_id,
                        vehicle_rz_note=(note or "")[:200],
                        row_kind=row_kind,
                        sort_order=order,
                        assignment_weight=max(0, min(9, int(weight or 0))),
                    )
                )
                order += 1

        for subject_id, vehicle_kind_id, slots in standard_rows:
            _append(subject_id, vehicle_kind_id, slots, SvozYardDriverPlan.RowKind.STANDARD)

        if exception_pair_slots:
            # UNIQUE (den, dvůr, skupina, druh vozidla, sort_order) — stejný řidič může být na V1 i V2.
            seen_exc_slot: set[tuple[int, int, int]] = set()
            for subject_id, vehicle_kind_id, sort_order, slot in exception_pair_slots:
                driver_id, rz_id, note = slot
                if not driver_id:
                    continue
                key = (subject_id, vehicle_kind_id, int(sort_order))
                if key in seen_exc_slot:
                    continue
                seen_exc_slot.add(key)
                bulk.append(
                    SvozYardDriverPlan(
                        plan_date=plan_date,
                        subject_profile_id=subject_id,
                        vehicle_kind_id=vehicle_kind_id,
                        driver_id=driver_id,
                        vehicle_rz_id=rz_id,
                        vehicle_rz_note=(note or "")[:200],
                        row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
                        sort_order=int(sort_order),
                        assignment_weight=1,
                    )
                )
        elif exception_rows:
            for subject_id, vehicle_kind_id, slots in exception_rows:
                _append(subject_id, vehicle_kind_id, slots, SvozYardDriverPlan.RowKind.EXCEPTION)

        if bulk:
            SvozYardDriverPlan.objects.bulk_create(bulk)
