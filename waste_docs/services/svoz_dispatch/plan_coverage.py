"""Kontrola, zda denní plán pokrývá kombinace dvůr × druh vozidla × běžný/výjimka z matice."""

from __future__ import annotations

from collections import defaultdict

from django.db.utils import OperationalError

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair, VehicleKindCatalog
from waste_docs.models import SvozPlanDriverPoolAcknowledgement, SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.exception_slot import (
    exception_slot_for_pair,
    matrix_pair_display_label,
    plan_sort_order_from_slot,
)


def _row_kind_value(row_kind) -> str:
    """Hodnota do DB/URL vždy jako řetězec (standard|exception), ne enum instance."""
    if isinstance(row_kind, str):
        return row_kind
    return getattr(row_kind, "value", str(row_kind))


def required_plan_keys(yard_ids: list[int]) -> set[tuple[int, int, str]]:
    """(subject_profile_id, vehicle_kind_id, row_kind) z číselníkových párů se zapnutým svozem (běžný svoz)."""
    if not yard_ids:
        return set()
    keys: set[tuple[int, int, str]] = set()
    for sid, vk_id, auto in NameSubjectWasteSuffixPair.objects.filter(
        subject_profile_id__in=yard_ids,
        yard_svoz_enabled=True,
        yard_vehicle_kind_id__isnull=False,
    ).values_list("subject_profile_id", "yard_vehicle_kind_id", "yard_svoz_auto_assign_driver"):
        if auto:
            keys.add((sid, int(vk_id), _row_kind_value(SvozYardDriverPlan.RowKind.STANDARD)))
    return keys


def required_exception_slot_keys(yard_ids: list[int]) -> list[dict]:
    """
    Výjimkové řádky matice s přiřazeným slotem V1–V4 — každý vyžaduje řidiče+RZ v plánu.

    Položka: subject_profile_id, vehicle_kind_id, sort_order, slot (1–4), matrix_label.
    """
    if not yard_ids:
        return []
    out: list[dict] = []
    pairs = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id__in=yard_ids,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind_id__isnull=False,
        )
        .select_related("waste_type", "suffix", "yard_vehicle_kind")
        .order_by("subject_profile_id", "yard_vehicle_kind_id", "yard_svoz_exception_slot", "sort_order")
    )
    for pair in pairs:
        slot = exception_slot_for_pair(pair)
        if slot is None:
            continue
        out.append(
            {
                "subject_profile_id": pair.subject_profile_id,
                "vehicle_kind_id": int(pair.yard_vehicle_kind_id),
                "sort_order": plan_sort_order_from_slot(slot),
                "slot": slot,
                "matrix_label": matrix_pair_display_label(pair),
            }
        )
    return out


def _yard_company_map(yard_ids: list[int]) -> dict[int, str]:
    return dict(
        NameSubjectProfile.objects.filter(pk__in=yard_ids).values_list("pk", "company_name")
    )


def _vehicle_kind_labels(vk_ids: set[int]) -> dict[int, str]:
    if not vk_ids:
        return {}
    return {
        k.pk: f"{k.shortcut} — {k.name}"
        for k in VehicleKindCatalog.objects.filter(pk__in=vk_ids).only("pk", "name", "shortcut")
    }


def plan_has_driver_pool(
    *,
    plan_date,
    subject_profile_id: int,
    vehicle_kind_id: int,
    row_kind: str,
) -> bool:
    """Stejná logika párování jako u matice požadavku / přiřazení úkolu."""
    from waste_docs.services.svoz_dispatch.plan_row_resolution import resolve_svoz_plan_rows

    rows = resolve_svoz_plan_rows(
        plan_date=plan_date,
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=vehicle_kind_id,
        row_kind=row_kind,
    )
    return any(r.driver_id and r.vehicle_rz_id for r in rows)


def plan_has_driver_for_exception_slot(
    *,
    plan_date,
    subject_profile_id: int,
    vehicle_kind_id: int,
    sort_order: int,
) -> bool:
    """Je ve výjimkovém plánu vyplněn řidič+RZ pro konkrétní slot (sort_order 0–3)?"""
    from waste_docs.services.svoz_dispatch.plan_row_resolution import resolve_svoz_plan_rows

    rows = resolve_svoz_plan_rows(
        plan_date=plan_date,
        subject_profile_id=subject_profile_id,
        yard_vehicle_kind_id=vehicle_kind_id,
        row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
    )
    for row in rows:
        if row.sort_order == sort_order and row.driver_id and row.vehicle_rz_id:
            return True
    return False


def _acknowledged_gap_keys(plan_date) -> set[tuple[int, int, str]]:
    try:
        return set(
            SvozPlanDriverPoolAcknowledgement.objects.filter(plan_date=plan_date).values_list(
                "subject_profile_id", "vehicle_kind_id", "row_kind"
            )
        )
    except OperationalError:
        # Tabulka ještě neexistuje (neproběhla migrace) — chování jako bez potvrzení.
        return set()


def plan_coverage_has_any_gap(plan_date, yard_ids: list[int]) -> bool:
    """Rychlá kontrola pro dashboard — skončí po první nalezené mezeře."""
    if not yard_ids:
        return False

    from waste_docs.services.svoz_dispatch.plan_day_cache import (
        DayPlanResolveCache,
        plan_has_driver_for_exception_slot_cached,
        plan_has_driver_pool_cached,
    )

    cache = DayPlanResolveCache.load(plan_date)
    required = required_plan_keys(yard_ids)
    acked = _acknowledged_gap_keys(plan_date)

    for sid, vk_id, rk in required:
        rk_s = _row_kind_value(rk)
        if (sid, vk_id, rk_s) in acked:
            continue
        if not plan_has_driver_pool_cached(
            cache,
            subject_profile_id=sid,
            vehicle_kind_id=vk_id,
            row_kind=rk_s,
        ):
            return True

    for ex in required_exception_slot_keys(yard_ids):
        sid = ex["subject_profile_id"]
        vk_id = ex["vehicle_kind_id"]
        rk_s = _row_kind_value(SvozYardDriverPlan.RowKind.EXCEPTION)
        if (sid, vk_id, rk_s) in acked:
            continue
        if not plan_has_driver_for_exception_slot_cached(
            cache,
            subject_profile_id=sid,
            vehicle_kind_id=vk_id,
            sort_order=ex["sort_order"],
        ):
            return True

    if (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            assigned_driver__isnull=True,
            subject_profile_id__in=yard_ids,
        )
        .exists()
    ):
        return True

    return False


def plan_coverage_gap_items(plan_date, yard_ids: list[int]) -> list[dict]:
    """
    Položky pro zobrazení na plánu svozů.

    Každá má ``text`` a volitelně ``gap`` (subject_profile_id, vehicle_kind_id, row_kind)
    pro formulář „Potvrdit výjimku“ — po potvrzení dispečerem se upozornění pro tuto
    kombinaci v daný den nezobrazí.
    """
    from waste_docs.services.svoz_dispatch.plan_day_cache import (
        DayPlanResolveCache,
        plan_has_driver_for_exception_slot_cached,
        plan_has_driver_pool_cached,
    )

    items: list[dict] = []
    yards = _yard_company_map(yard_ids)
    required = required_plan_keys(yard_ids)
    vk_labels = _vehicle_kind_labels({k[1] for k in required})
    acked = _acknowledged_gap_keys(plan_date)
    cache = DayPlanResolveCache.load(plan_date)

    for sid, vk_id, rk in sorted(required, key=lambda t: (t[0], t[1], t[2])):
        rk_s = _row_kind_value(rk)
        if plan_has_driver_pool_cached(
            cache,
            subject_profile_id=sid,
            vehicle_kind_id=vk_id,
            row_kind=rk_s,
        ):
            continue
        if (sid, vk_id, rk_s) in acked:
            continue
        yname = yards.get(sid, f"dvůr #{sid}")
        vkname = vk_labels.get(vk_id, f"druh #{vk_id}")
        try:
            plan_group_label = SvozYardDriverPlan.RowKind(rk_s).label
        except ValueError:
            plan_group_label = str(rk_s)
        items.append(
            {
                "item_type": "driver_pool",
                "subject_profile_id": sid,
                "yard_name": yname,
                "vehicle_kind_label": vkname,
                "plan_group_label": plan_group_label,
                "text": (
                    f"{yname}: pro {vkname} chybí řidiči v plánu ({plan_group_label}). "
                    "Jde-li o záměr, můžete potvrdit výjimku."
                ),
                "gap": {
                    "subject_profile_id": sid,
                    "vehicle_kind_id": vk_id,
                    "row_kind": rk_s,
                },
            }
        )

    ex_slots = required_exception_slot_keys(yard_ids)
    vk_labels_ex = _vehicle_kind_labels({e["vehicle_kind_id"] for e in ex_slots})
    for ex in ex_slots:
        sid = ex["subject_profile_id"]
        vk_id = ex["vehicle_kind_id"]
        rk_s = _row_kind_value(SvozYardDriverPlan.RowKind.EXCEPTION)
        if plan_has_driver_for_exception_slot_cached(
            cache,
            subject_profile_id=sid,
            vehicle_kind_id=vk_id,
            sort_order=ex["sort_order"],
        ):
            continue
        if (sid, vk_id, rk_s) in acked:
            continue
        yname = yards.get(sid, f"dvůr #{sid}")
        vkname = vk_labels_ex.get(vk_id, f"druh #{vk_id}")
        slot_label = f"V{ex['slot']}"
        items.append(
            {
                "item_type": "driver_pool",
                "subject_profile_id": sid,
                "yard_name": yname,
                "vehicle_kind_label": vkname,
                "plan_group_label": f"Výjimky — {slot_label}",
                "text": (
                    f"{yname}: pro {vkname} ve slotu {slot_label} ({ex['matrix_label']}) "
                    "chybí řidič a RZ v plánu výjimek."
                ),
                "gap": {
                    "subject_profile_id": sid,
                    "vehicle_kind_id": vk_id,
                    "row_kind": rk_s,
                },
            }
        )

    open_no_driver = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            assigned_driver__isnull=True,
            subject_profile_id__in=yard_ids,
        )
        .values_list("subject_profile_id", flat=True)
        .distinct()
    )
    yard_hits = set(open_no_driver)
    if yard_hits:
        for sid in sorted(yard_hits):
            yname = yards.get(sid, f"dvůr #{sid}")
            items.append(
                {
                    "item_type": "open_tasks",
                    "subject_profile_id": sid,
                    "yard_name": yname,
                    "vehicle_kind_label": "—",
                    "plan_group_label": "—",
                    "text": f"{yname}: jsou otevřené požadavky na svoz bez přiřazeného řidiče.",
                    "gap": None,
                }
            )

    return items


def plan_coverage_warnings(plan_date, yard_ids: list[int]) -> list[str]:
    """Zpětná kompatibilita — pouze texty upozornění."""
    return [item["text"] for item in plan_coverage_gap_items(plan_date, yard_ids)]


def yard_ids_with_svoz_exception_matrix_rows(yard_ids: list[int]) -> set[int]:
    """
    Dvory, u kterých existuje v matici alespoň jeden řádek se zapnutým svozem
    a vypnutým „běžným svozem“ (výjimka) — pro ty se v plánu zobrazí sloupce Výjimky.
    """
    if not yard_ids:
        return set()
    return set(
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id__in=yard_ids,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
        )
        .values_list("subject_profile_id", flat=True)
        .distinct()
    )


def vehicle_kinds_by_yard(yard_ids: list[int]) -> dict[int, list[VehicleKindCatalog]]:
    """
    Druhy vozidel pro běžný svoz (B1–B4) — jen z řádků matice se zapnutým běžným svozem.

    Např. Lisovací na 3H → řádek 3H nahoře; výjimky (Matrace / V-slot) sem nepatří.
    """
    from catalogs.services.name_subject_pair_vehicle_kinds import pair_vehicle_kind_ids

    if not yard_ids:
        return {}
    pairs = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id__in=yard_ids,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=True,
        )
        .prefetch_related("yard_vehicle_kinds")
        .select_related("yard_vehicle_kind")
    )
    yard_to_vkids: dict[int, set[int]] = defaultdict(set)
    for pair in pairs:
        for vk_id in pair_vehicle_kind_ids(pair):
            yard_to_vkids[pair.subject_profile_id].add(vk_id)
    all_vk = {vk for ids in yard_to_vkids.values() for vk in ids}
    kinds_by_pk = {
        k.pk: k
        for k in VehicleKindCatalog.objects.filter(pk__in=all_vk).order_by(
            "sort_order", "name", "pk"
        )
    }
    out: dict[int, list[VehicleKindCatalog]] = {}
    for yid in yard_ids:
        kids = yard_to_vkids.get(yid, set())
        out[yid] = sorted(
            (kinds_by_pk[k] for k in kids if k in kinds_by_pk),
            key=lambda k: (k.sort_order, k.name, k.pk),
        )
    return out
