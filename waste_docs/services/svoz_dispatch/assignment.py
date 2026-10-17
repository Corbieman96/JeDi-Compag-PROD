"""Přiřazení řidiče a RZ vozidla k otevřenému požadavku na svoz (plán dvora)."""

from __future__ import annotations

from django.db.models import Count, Q

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.ratio_threshold import resolve_standard_assignment_plan_rows
from waste_docs.services.svoz_dispatch.exception_slot import (
    exception_slot_for_pair,
    plan_sort_order_from_slot,
)
from waste_docs.services.svoz_dispatch.plan_row_resolution import (
    resolve_svoz_plan_rows,
    resolve_svoz_plan_rows_for_assignment,
)
from waste_docs.services.svoz_dispatch.weighted_assignment import pick_weighted_assignment
from waste_docs.services.svoz_task_auto_pruvodka import try_create_pruvodka_for_assigned_svoz_task


def _pair_for_task(task: SvozTask) -> NameSubjectWasteSuffixPair | None:
    if task.source_waste_suffix_pair_id:
        return (
            NameSubjectWasteSuffixPair.objects.filter(pk=task.source_waste_suffix_pair_id)
            .only(
                "pk",
                "yard_svoz_auto_assign_driver",
                "yard_svoz_exception_slot",
                "subject_profile_id",
                "waste_type_id",
                "suffix_id",
            )
            .first()
        )
    return (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id=task.subject_profile_id,
            waste_type_id=task.waste_type_id,
            suffix_id=task.suffix_id,
        )
        .only(
            "pk",
            "yard_svoz_auto_assign_driver",
            "yard_svoz_exception_slot",
            "subject_profile_id",
            "waste_type_id",
            "suffix_id",
        )
        .first()
    )


def _svoz_plan_rows(
    task: SvozTask,
    *,
    yard_svoz_auto_assign_driver: bool,
    pair: NameSubjectWasteSuffixPair | None = None,
):
    return resolve_svoz_plan_rows_for_assignment(
        plan_date=task.target_date,
        subject_profile_id=int(task.subject_profile_id),
        yard_vehicle_kind_id=int(task.vehicle_kind_id) if task.vehicle_kind_id else None,
        yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
        pair=pair,
    )


def _assignment_from_exception_slot(
    task: SvozTask,
    slot: int,
    *,
    yard_svoz_auto_assign_driver: bool,
    pair: NameSubjectWasteSuffixPair | None = None,
) -> tuple[int | None, int | None]:
    """
    Přiřazení z výjimkového plánu — vyžaduje řidiče i RZ.

    Nejprve slot V úkolu (V1→sort_order 0); pokud u něj plán chybí, první vyplněný
    V-slot téhož dvora a druhu vozidla (stejný dispečerský plán výjimek).
    """
    plan_rows = _svoz_plan_rows(
        task,
        yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
        pair=pair,
    )
    if not plan_rows:
        return None, None
    want_order = plan_sort_order_from_slot(slot)
    fallback: tuple[int | None, int | None] | None = None
    for row in sorted(plan_rows, key=lambda r: (r.sort_order, r.pk)):
        if not row.driver_id or not row.vehicle_rz_id:
            continue
        if row.sort_order == want_order:
            return row.driver_id, row.vehicle_rz_id
        if fallback is None:
            fallback = (row.driver_id, row.vehicle_rz_id)
    return fallback if fallback else (None, None)


def _vehicle_rz_id_from_plan_for_assigned_driver(
    task: SvozTask,
    *,
    yard_svoz_auto_assign_driver: bool,
    pair: NameSubjectWasteSuffixPair | None = None,
) -> int | None:
    """
    RZ z uloženého plánu — první slot pro daný dvůr/kind/skupinu, kde je stejný řidič jako na úkolu
    a v slotu je neprázdné RZ.
    """
    if pair is None:
        pair = _pair_for_task(task)
    if pair and not yard_svoz_auto_assign_driver:
        slot = exception_slot_for_pair(pair)
        if slot is not None:
            _d, rz_id = _assignment_from_exception_slot(
                task,
                slot,
                yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
                pair=pair,
            )
            if rz_id and task.assigned_driver_id:
                plan_rows = _svoz_plan_rows(
                    task,
                    yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
                    pair=pair,
                )
                want_order = plan_sort_order_from_slot(slot)
                for row in plan_rows:
                    if (
                        row.sort_order == want_order
                        and row.driver_id == task.assigned_driver_id
                        and row.vehicle_rz_id
                    ):
                        return int(row.vehicle_rz_id)
            return rz_id

    for row in _svoz_plan_rows(
        task,
        yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
        pair=pair,
    ):
        if row.driver_id != task.assigned_driver_id:
            continue
        rid = getattr(row, "vehicle_rz_id", None)
        if rid:
            return int(rid)
    return None


def _pick_round_robin_assignment(
    task: SvozTask,
    *,
    yard_svoz_auto_assign_driver: bool,
    pair: NameSubjectWasteSuffixPair | None = None,
) -> tuple[int | None, int | None]:
    """Vrátí (driver_id, vehicle_rz_id) podle plánu a rozložení otevřených úkolů."""
    if pair is None:
        pair = _pair_for_task(task) if getattr(task, "pk", None) else None
    if pair and not yard_svoz_auto_assign_driver:
        slot = exception_slot_for_pair(pair)
        if slot is not None:
            return _assignment_from_exception_slot(
                task,
                slot,
                yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
                pair=pair,
            )

    plan_rows = _svoz_plan_rows(
        task,
        yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
        pair=pair,
    )
    if not plan_rows:
        return None, None
    driver_ids = [r.driver_id for r in plan_rows]
    counts_filter = Q(
        subject_profile_id=task.subject_profile_id,
        target_date=task.target_date,
        status__in=(SvozTask.Status.OPEN, SvozTask.Status.DONE),
        assigned_driver_id__in=driver_ids,
    )
    if task.vehicle_kind_id:
        counts_filter &= Q(vehicle_kind_id=task.vehicle_kind_id)
    else:
        counts_filter &= Q(vehicle_kind__isnull=True)
    counts_qs = (
        SvozTask.objects.filter(counts_filter)
        .values("assigned_driver_id", "assigned_vehicle_rz_id")
        .annotate(cnt=Count("pk"))
    )
    counts = {(row["assigned_driver_id"], row["assigned_vehicle_rz_id"]): row["cnt"] for row in counts_qs}
    profile = (
        NameSubjectProfile.objects.filter(pk=task.subject_profile_id)
        .select_related("yard_settings")
        .first()
    )
    rows_for_pick = resolve_standard_assignment_plan_rows(
        plan_rows,
        plan_date=task.target_date,
        subject_profile_id=int(task.subject_profile_id),
        vehicle_kind_id=int(task.vehicle_kind_id) if task.vehicle_kind_id else None,
        yard_settings=profile.yard_settings if profile else None,
    )
    return pick_weighted_assignment(rows_for_pick, counts)


def planned_assignment_for_matrix_row(
    *,
    subject_profile_id: int,
    target_date,
    vehicle_kind_id: int | None,
    yard_svoz_auto_assign_driver: bool,
    pair: NameSubjectWasteSuffixPair | None = None,
) -> tuple[int | None, int | None]:
    """
    Jaké (řidič, RZ) by plán svozů přiřadil k novému úkolu s daným dvorem, dnem a druhem vozidla.
    Používá stejnou logiku jako assign_driver_for_new_task (round-robin podle otevřených úkolů).
    """
    from types import SimpleNamespace

    task = SimpleNamespace(
        subject_profile_id=subject_profile_id,
        target_date=target_date,
        vehicle_kind_id=vehicle_kind_id,
    )
    return _pick_round_robin_assignment(
        task,
        yard_svoz_auto_assign_driver=yard_svoz_auto_assign_driver,
        pair=pair,
    )


def assign_driver_for_new_task(task: SvozTask, pair: NameSubjectWasteSuffixPair, *, actor=None) -> str | None:
    """
    Nastaví `assigned_driver` a `assigned_vehicle_rz` u nově vytvořeného úkolu.

    Vrací text chyby, pokud byl řidič přiřazen, ale automatické založení jízdy selhalo kvůli validaci;
    jinak None.
    """
    if task.pk is None:
        raise ValueError("assign_driver_for_new_task očekává uložený SvozTask (s pk).")
    driver_id, rz_id = _pick_round_robin_assignment(
        task,
        yard_svoz_auto_assign_driver=pair.yard_svoz_auto_assign_driver,
        pair=pair,
    )
    if driver_id is None:
        return None
    SvozTask.objects.filter(pk=task.pk).update(
        assigned_driver_id=driver_id,
        assigned_vehicle_rz_id=rz_id,
    )
    task.assigned_driver_id = driver_id
    task.assigned_vehicle_rz_id = rz_id
    task.refresh_from_db(
        fields=[
            "assigned_driver_id",
            "assigned_vehicle_rz_id",
            "status",
            "activity_id",
            "target_date",
            "subject_profile_id",
            "waste_type_id",
            "suffix_id",
            "vehicle_kind_id",
            "resolved_pruvodka_id",
        ]
    )
    auto_ok, auto_err = try_create_pruvodka_for_assigned_svoz_task(task, actor or task.created_by)
    if auto_ok:
        return None
    # Po přiřazení z plánu vždy vrať důvod — ať SD / dispečer vidí, proč jízda nevznikla.
    return auto_err or "Automatické založení jízdy selhalo."


def _valid_plan_assignments_for_task(
    task: SvozTask,
    pair: NameSubjectWasteSuffixPair,
) -> tuple[set[int], set[tuple[int, int]]]:
    """Řidiči a dvojice (řidič, RZ) platné podle aktuálního denního plánu."""
    rows = _svoz_plan_rows(
        task,
        yard_svoz_auto_assign_driver=pair.yard_svoz_auto_assign_driver,
        pair=pair,
    )
    driver_ids = {int(r.driver_id) for r in rows if r.driver_id}
    pairs = {
        (int(r.driver_id), int(r.vehicle_rz_id))
        for r in rows
        if r.driver_id and r.vehicle_rz_id
    }
    return driver_ids, pairs


def reconcile_open_tasks_with_plan_for_plan_date(plan_date, actor=None) -> int:
    """
    Po změně plánu srovná otevřené požadavky bez průvodky s aktuálními sloty.

    Úkoly přiřazené řidiči, který už v plánu není, se přeřadí (round-robin) nebo
    se jim zruší přiřazení, pokud plán pro daný dvůr/druh neobsahuje žádného řidiče.
    """
    updated = 0
    refresh_fields = [
        "assigned_driver_id",
        "assigned_vehicle_rz_id",
        "status",
        "activity_id",
        "target_date",
        "subject_profile_id",
        "waste_type_id",
        "suffix_id",
        "vehicle_kind_id",
        "resolved_pruvodka_id",
    ]
    tasks = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            resolved_pruvodka__isnull=True,
            assigned_driver__isnull=False,
        )
        .select_related("source_waste_suffix_pair")
        .order_by("pk")
    )
    for task in tasks:
        pair = _pair_for_task(task)
        if not pair:
            continue
        auto_flag = pair.yard_svoz_auto_assign_driver
        driver_ids, valid_pairs = _valid_plan_assignments_for_task(task, pair)

        if task.assigned_driver_id not in driver_ids:
            driver_id, rz_id = _pick_round_robin_assignment(
                task,
                yard_svoz_auto_assign_driver=auto_flag,
                pair=pair,
            )
            if driver_id is None:
                if task.assigned_driver_id or task.assigned_vehicle_rz_id:
                    SvozTask.objects.filter(pk=task.pk).update(
                        assigned_driver_id=None,
                        assigned_vehicle_rz_id=None,
                    )
                    updated += 1
            elif (
                task.assigned_driver_id != driver_id
                or task.assigned_vehicle_rz_id != rz_id
            ):
                SvozTask.objects.filter(pk=task.pk).update(
                    assigned_driver_id=driver_id,
                    assigned_vehicle_rz_id=rz_id,
                )
                updated += 1
                task.refresh_from_db(fields=refresh_fields)
                who = actor or task.created_by
                try_create_pruvodka_for_assigned_svoz_task(task, who)
            continue

        if task.assigned_vehicle_rz_id and (
            task.assigned_driver_id,
            task.assigned_vehicle_rz_id,
        ) in valid_pairs:
            continue

        rz_id = _vehicle_rz_id_from_plan_for_assigned_driver(
            task,
            yard_svoz_auto_assign_driver=auto_flag,
            pair=pair,
        )
        if rz_id and task.assigned_vehicle_rz_id != rz_id:
            SvozTask.objects.filter(pk=task.pk).update(assigned_vehicle_rz_id=rz_id)
            updated += 1
            task.refresh_from_db(fields=refresh_fields)
            who = actor or task.created_by
            try_create_pruvodka_for_assigned_svoz_task(task, who)
    return updated


def rebalance_standard_open_tasks_for_plan_date(plan_date, actor=None) -> int:
    """
    Přepočítá přiřazení řidiče u otevřených běžných požadavků bez průvodky
    podle aktuálního plánu a vah (poměr B1:B2).
  """
    from collections import defaultdict

    tasks = list(
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            resolved_pruvodka__isnull=True,
        )
        .select_related("source_waste_suffix_pair")
        .order_by("pk")
    )
    groups: dict[tuple[int, int | None], list[SvozTask]] = defaultdict(list)
    for task in tasks:
        pair = _pair_for_task(task)
        if not pair or not pair.yard_svoz_auto_assign_driver:
            continue
        groups[(int(task.subject_profile_id), task.vehicle_kind_id)].append(task)

    updated = 0
    yard_settings_cache: dict[int, object] = {}
    refresh_fields = [
        "assigned_driver_id",
        "assigned_vehicle_rz_id",
        "status",
        "activity_id",
        "target_date",
        "subject_profile_id",
        "waste_type_id",
        "suffix_id",
        "vehicle_kind_id",
        "resolved_pruvodka_id",
    ]
    for (subject_id, vk_id), group_tasks in groups.items():
        plan_rows = resolve_svoz_plan_rows(
            plan_date=plan_date,
            subject_profile_id=subject_id,
            yard_vehicle_kind_id=vk_id,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
        )
        filled_rows = [r for r in plan_rows if r.driver_id]
        if len(filled_rows) < 1:
            continue
        if subject_id not in yard_settings_cache:
            profile = (
                NameSubjectProfile.objects.filter(pk=subject_id)
                .select_related("yard_settings")
                .first()
            )
            yard_settings_cache[subject_id] = profile.yard_settings if profile else None
        rows_for_pick = resolve_standard_assignment_plan_rows(
            filled_rows,
            plan_date=plan_date,
            subject_profile_id=subject_id,
            vehicle_kind_id=vk_id,
            yard_settings=yard_settings_cache[subject_id],
        )

        counts: dict[tuple[int | None, int | None], int] = {}
        for task in group_tasks:
            driver_id, rz_id = pick_weighted_assignment(rows_for_pick, counts)
            if driver_id is None:
                continue
            key = (driver_id, rz_id)
            counts[key] = counts.get(key, 0) + 1
            if task.assigned_driver_id == driver_id and task.assigned_vehicle_rz_id == rz_id:
                continue
            SvozTask.objects.filter(pk=task.pk).update(
                assigned_driver_id=driver_id,
                assigned_vehicle_rz_id=rz_id,
            )
            updated += 1
            task.refresh_from_db(fields=refresh_fields)
            who = actor or task.created_by
            try_create_pruvodka_for_assigned_svoz_task(task, who)
    return updated


def backfill_open_tasks_for_plan_date(plan_date, actor=None) -> tuple[int, list[str]]:
    """
    Podle uloženého denního plánu doplní řidiče a/nebo RZ na otevřených úkolech bez průvodky.

    Bez řidiče: round-robin z plánu (jako při vzniku požadavku). Už má řidiče, ale chybí RZ:
    RZ se vezme ze stejného plánu z prvního slotu daného řidiče s neprázdným RZ (typicky doplnění
    po druhém uložení plánu, kde už RZ u slotů je).

    Vrací (počet aktualizovaných přiřazení, krátké zprávy o neúspěchu auto-založení jízdy).
    """
    updated = 0
    ride_errors: list[str] = []
    candidates = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            resolved_pruvodka__isnull=True,
        )
        .filter(
            Q(assigned_driver__isnull=True)
            | Q(assigned_vehicle_rz__isnull=True),
        )
        .select_related("subject_profile", "source_waste_suffix_pair")
        .order_by("pk")
    )
    refresh_fields = [
        "assigned_driver_id",
        "assigned_vehicle_rz_id",
        "status",
        "activity_id",
        "target_date",
        "subject_profile_id",
        "waste_type_id",
        "suffix_id",
        "vehicle_kind_id",
        "resolved_pruvodka_id",
    ]
    for task in candidates:
        pair = _pair_for_task(task)
        if not pair:
            continue
        auto_flag = pair.yard_svoz_auto_assign_driver
        if task.assigned_driver_id is None:
            driver_id, rz_id = _pick_round_robin_assignment(
                task,
                yard_svoz_auto_assign_driver=auto_flag,
                pair=pair,
            )
            if driver_id is None:
                continue
            SvozTask.objects.filter(pk=task.pk).update(
                assigned_driver_id=driver_id,
                assigned_vehicle_rz_id=rz_id,
            )
            updated += 1
        elif task.assigned_vehicle_rz_id is None:
            rz_id = _vehicle_rz_id_from_plan_for_assigned_driver(
                task,
                yard_svoz_auto_assign_driver=auto_flag,
                pair=pair,
            )
            if rz_id is None:
                continue
            SvozTask.objects.filter(pk=task.pk).update(assigned_vehicle_rz_id=rz_id)
            updated += 1
        else:
            continue
        task.refresh_from_db(fields=refresh_fields)
        who = actor or task.created_by
        ok_auto, err_auto = try_create_pruvodka_for_assigned_svoz_task(task, who)
        if not ok_auto and err_auto:
            ride_errors.append(f"Úkol #{task.pk}: {err_auto}")
    return updated, ride_errors


def auto_create_rides_for_assigned_tasks_on_date(plan_date, actor=None) -> tuple[int, list[str]]:
    """
    Pro otevřené úkoly daného dne se zadaným řidičem a RZ založí jízdu (pokud ještě nevznikla).

    Na obrazovce plánu (`/waste-docs/svoz-plan/?date`) se ke každému sběrnému dvoru v jeho bloku nastavuje
    kombinace řidič + RZ v jednotlivých slotech (druh vozidla, běžný svoz / výjimka). Ta se po uložení
    plánu promítne přes `backfill_open_tasks_for_plan_date` do přiřazení otevřených požadavků (odpovídající dvůr a den realizace).
    Pro auto-založení jízdy musí už na úkolu být obojí (`assigned_driver`, `assigned_vehicle_rz`): pokud v plánu
    u příslušné kombinace chybí RZ u slotu řidiče, úkol RZ nedostane ani se do auto-create nezahrne.

    Vrací (počet nově založených jízd, krátké zprávy o neúspěšné validaci).
    """
    created = 0
    ride_errors: list[str] = []
    candidates = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            assigned_driver__isnull=False,
            assigned_vehicle_rz__isnull=False,
            resolved_pruvodka__isnull=True,
            activity__isnull=False,
        )
        .select_related("created_by")
        .order_by("pk")
    )
    for task in candidates:
        who = actor or task.created_by
        ok, err = try_create_pruvodka_for_assigned_svoz_task(task, who)
        if ok:
            created += 1
        elif err:
            ride_errors.append(f"Úkol #{task.pk}: {err}")
    return created, ride_errors
