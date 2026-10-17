"""Obrazovka denního plánu řidičů a RZ vozidel u sběrných dvorů (dispečer)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from catalogs.models import NameSubjectProfile
from catalogs.services.driver_absence import driver_ids_hidden_from_drivers_panel
from users.services.access import can_see_all_waste_docs
from waste_docs.models import SvozPlanDriverPoolAcknowledgement, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import (
    auto_create_rides_for_assigned_tasks_on_date,
    backfill_open_tasks_for_plan_date,
    rebalance_standard_open_tasks_for_plan_date,
    reconcile_open_tasks_with_plan_for_plan_date,
    replace_yard_driver_plan_for_date,
)
from waste_docs.services.svoz_dispatch.ratio_quotas import (
    RATIO_CUSTOM_VALUE,
    build_svoz_ratio_client_config,
    effective_ratio_hint,
    is_ratio_in_presets,
    ratio_label_for_slot_count,
    ratio_label_from_weights,
    ratio_presets_for_slot_count,
    resolve_ratio_from_post,
    validate_ratio_for_slots,
)
from waste_docs.services.svoz_dispatch.ratio_threshold import (
    ratio_applies,
    ratio_inactive_hint,
    ratio_min_containers_for_yard,
    ratio_min_for_yard_in_plan,
    save_yard_ratio_mins_from_plan_post,
    validate_yard_ratio_mins_from_plan_post,
    weights_for_plan_slots,
)
from waste_docs.services.svoz_dispatch.standard_tasks_preview import (
    open_standard_tasks_preview_for_yard_kind,
)
from waste_docs.services.svoz_dispatch.plan import validate_plan_driver_uniqueness
from waste_docs.services.svoz_dispatch.driver_vehicle_kind import (
    driver_queryset_for_vehicle_kind,
    drivers_for_dispatch_plan_kind_section,
    validate_plan_drivers_for_vehicle_kinds,
    vehicle_rz_queryset_for_vehicle_kind,
    vehicle_rzs_for_dispatch_plan_section,
)

from catalogs.models import NameSubjectWasteSuffixPair

from waste_docs.services.svoz_dispatch.exception_slot import (
    exception_matrix_pairs_by_yard,
    exception_plan_badge_summary,
    exception_slot_for_pair,
    group_exception_sections_by_vehicle_kind,
    open_tasks_preview_for_matrix_pair,
    plan_assignment_for_exception_pair,
    plan_sort_order_from_slot,
)
from waste_docs.services.svoz_dispatch.plan_coverage import (
    plan_coverage_gap_items,
    required_exception_slot_keys,
    required_plan_keys,
    vehicle_kinds_by_yard,
)
from waste_docs.services.svoz_dispatch.plan_vehicle_rz_day_hints import (
    vehicle_rz_ids_multi_assigned_in_plan,
    vehicle_rz_ids_with_pruvodka_on_date,
)

_MAX_DRIVERS_PER_YARD = 4


def _collect_exception_plan_by_matrix_pairs(
    request,
    yard_ids: list[int],
) -> list[tuple[int, int, int, tuple[int, int | None, str]]]:
    """(subject_id, vehicle_kind_id, sort_order, (driver_id, rz_id, note)) pro výjimkové řádky matice."""
    if not yard_ids:
        return []
    out: list[tuple[int, int, int, tuple[int, int | None, str]]] = []
    pairs = NameSubjectWasteSuffixPair.objects.filter(
        subject_profile_id__in=yard_ids,
        yard_svoz_enabled=True,
        yard_svoz_auto_assign_driver=False,
        yard_vehicle_kind_id__isnull=False,
    ).only("pk", "subject_profile_id", "yard_vehicle_kind_id", "yard_svoz_exception_slot", "yard_svoz_auto_assign_driver")
    for pair in pairs:
        slot = exception_slot_for_pair(pair)
        if slot is None:
            continue
        yid = pair.subject_profile_id
        did_raw = (request.POST.get(f"expair_drv_{yid}_{pair.pk}") or "").strip()
        rz_raw = (request.POST.get(f"expair_vrz_{yid}_{pair.pk}") or "").strip()
        note_raw = (request.POST.get(f"expair_vrzn_{yid}_{pair.pk}") or "").strip()[:200]
        if not did_raw.isdigit():
            continue
        rz_id = int(rz_raw) if rz_raw.isdigit() else None
        out.append(
            (
                yid,
                int(pair.yard_vehicle_kind_id),
                plan_sort_order_from_slot(slot),
                (int(did_raw), rz_id, note_raw),
            )
        )
    return out


def _exception_pair_slots_as_rows(
    pair_slots: list[tuple[int, int, int, tuple[int, int | None, str]]],
) -> list[tuple[int, int, list[tuple[int, int | None, str]]]]:
    """Pro validaci — seskupí výjimky podle dvora a druhu vozidla."""
    grouped: dict[tuple[int, int], dict[int, tuple[int, int | None, str]]] = defaultdict(dict)
    for yid, vk_id, sort_order, slot in pair_slots:
        grouped[(yid, vk_id)][sort_order] = slot
    rows: list[tuple[int, int, list[tuple[int, int | None, str]]]] = []
    for (yid, vk_id), slots_map in grouped.items():
        slots = [slots_map[i] for i in sorted(slots_map.keys()) if slots_map[i][0]]
        if slots:
            rows.append((yid, vk_id, slots))
    return rows


def _validate_plan_ratios(
    request,
    yards: list[NameSubjectProfile],
    kinds_map: dict[int, list],
    *,
    plan_date,
) -> str | None:
    for y in yards:
        ratio_min = ratio_min_for_yard_in_plan(
            yard_id=y.pk,
            yard_settings=getattr(y, "yard_settings", None),
            post_data=request.POST,
        )
        for vk in kinds_map.get(y.pk, []):
            seen_d: set[int] = set()
            chosen_count = 0
            for i in range(_MAX_DRIVERS_PER_YARD):
                raw = (request.POST.get(f"drv_{y.pk}_{vk.pk}_{i}") or "").strip()
                if raw.isdigit():
                    did = int(raw)
                    if did in seen_d:
                        continue
                    seen_d.add(did)
                    chosen_count += 1
            if chosen_count < 2:
                continue
            open_count, _ = open_standard_tasks_preview_for_yard_kind(
                plan_date,
                subject_profile_id=y.pk,
                vehicle_kind_id=vk.pk,
            )
            if not ratio_applies(
                filled_driver_count=chosen_count,
                open_task_count=open_count,
                ratio_min=ratio_min,
            ):
                continue
            ratio = resolve_ratio_from_post(
                request.POST.get(f"ratio_{y.pk}_{vk.pk}", ""),
                request.POST.get(f"ratio_custom_{y.pk}_{vk.pk}", ""),
                chosen_count,
            )
            err = validate_ratio_for_slots(ratio, chosen_count)
            if err:
                yard_name = y.company_name or f"dvůr #{y.pk}"
                vk_label = vk.display_label() if hasattr(vk, "display_label") else str(vk)
                return f"{yard_name} / {vk_label}: {err}"
    return None


def _collect_plan_slots(
    request,
    yards: list[NameSubjectProfile],
    kinds_map: dict[int, list],
    drv_prefix: str,
    vrz_prefix: str,
    vrzn_prefix: str,
    *,
    exception_yards: set[int],
    plan_date,
):
    rows: list[tuple[int, int, list[tuple[int, int | None, str, int]]]] = []
    for y in yards:
        if drv_prefix == "exdrv" and y.pk not in exception_yards:
            continue
        for vk in kinds_map.get(y.pk, []):
            chosen: list[tuple[int, int | None, str]] = []
            seen_d: set[int] = set()
            for i in range(_MAX_DRIVERS_PER_YARD):
                raw = (request.POST.get(f"{drv_prefix}_{y.pk}_{vk.pk}_{i}") or "").strip()
                rz_raw = (request.POST.get(f"{vrz_prefix}_{y.pk}_{vk.pk}_{i}") or "").strip()
                note_raw = (request.POST.get(f"{vrzn_prefix}_{y.pk}_{vk.pk}_{i}") or "").strip()[:200]
                rz_id: int | None = int(rz_raw) if rz_raw.isdigit() else None
                if raw.isdigit():
                    did = int(raw)
                    if did in seen_d:
                        continue
                    seen_d.add(did)
                    chosen.append((did, rz_id, note_raw))
            open_count, _ = open_standard_tasks_preview_for_yard_kind(
                plan_date,
                subject_profile_id=y.pk,
                vehicle_kind_id=vk.pk,
            )
            ratio_min = ratio_min_for_yard_in_plan(
                yard_id=y.pk,
                yard_settings=getattr(y, "yard_settings", None),
                post_data=request.POST,
            )
            ratio_active = ratio_applies(
                filled_driver_count=len(chosen),
                open_task_count=open_count,
                ratio_min=ratio_min,
            )
            ratio = resolve_ratio_from_post(
                request.POST.get(f"ratio_{y.pk}_{vk.pk}", ""),
                request.POST.get(f"ratio_custom_{y.pk}_{vk.pk}", ""),
                len(chosen),
            )
            weights = weights_for_plan_slots(
                ratio=ratio,
                slot_count=len(chosen),
                ratio_active=ratio_active,
            )
            weighted = [
                (did, rz_id, note, weights[idx] if idx < len(weights) else 1)
                for idx, (did, rz_id, note) in enumerate(chosen)
            ]
            rows.append((y.pk, vk.pk, weighted))
    return rows


def _parse_plan_date(raw: str):
    if not (raw or "").strip():
        return timezone.localdate()
    try:
        return datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except ValueError:
        return timezone.localdate()


@login_required
def svoz_dispatch_plan(request):
    if not can_see_all_waste_docs(request.user):
        messages.error(request, "Plán svozů je dostupný jen dispečerovi nebo administrátorovi.")
        return redirect(reverse("core:dashboard"))

    plan_date = _parse_plan_date(request.GET.get("date") or request.POST.get("plan_date") or "")

    yards = list(
        NameSubjectProfile.objects.filter(yard_settings__is_collection_yard=True)
        .select_related("yard_settings")
        .order_by("company_name", "pk")
        .only("pk", "company_name", "yard_settings__yard_svoz_dispatch_group", "yard_settings__yard_svoz_ratio_min_containers")
    )
    yard_ids = [y.pk for y in yards]
    kinds_map = vehicle_kinds_by_yard(yard_ids)
    existing_standard: dict[tuple[int, int | None], list[tuple[int, int | None, str, int]]] = defaultdict(list)
    # výjimky: sort_order 0–3 (V1–V4) → (řidič, RZ, poznámka)
    existing_exception: dict[
        tuple[int, int | None],
        dict[int, tuple[int, int | None, str, int]],
    ] = defaultdict(dict)
    for r in SvozYardDriverPlan.objects.filter(
        plan_date=plan_date,
        subject_profile_id__in=yard_ids,
    ).order_by(
        "subject_profile_id",
        "row_kind",
        "vehicle_kind_id",
        "sort_order",
        "driver_id",
    ):
        key = (r.subject_profile_id, r.vehicle_kind_id)
        pair = (r.driver_id, r.vehicle_rz_id, (r.vehicle_rz_note or "").strip(), int(r.assignment_weight or 1))
        if str(r.row_kind) == SvozYardDriverPlan.RowKind.EXCEPTION.value:
            existing_exception[key][int(r.sort_order)] = pair
        else:
            existing_standard[key].append(pair)

    if request.method == "POST":
        if request.POST.get("revoke_pool_ack"):
            ack_raw = (request.POST.get("ack_id") or "").strip()
            if ack_raw.isdigit():
                n_del, _ = SvozPlanDriverPoolAcknowledgement.objects.filter(
                    pk=int(ack_raw),
                    plan_date=plan_date,
                    subject_profile_id__in=yard_ids,
                ).delete()
                if n_del:
                    messages.success(request, "Potvrzení výjimky bylo zrušeno — upozornění se znovu zobrazí, dokud znovu nepotvrdíte.")
                else:
                    messages.error(request, "Potvrzení se nepodařilo najít nebo už bylo odstraněno.")
            else:
                messages.error(request, "Neplatný požadavek na zrušení potvrzení.")
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")

        if request.POST.get("ack_pool_gap"):
            sid_raw = (request.POST.get("subject_profile_id") or "").strip()
            vk_raw = (request.POST.get("vehicle_kind_id") or "").strip()
            rk = (request.POST.get("row_kind") or "").strip()
            valid_rk = {c[0] for c in SvozYardDriverPlan.RowKind.choices}
            valid_keys = required_plan_keys(yard_ids)
            for ex in required_exception_slot_keys(yard_ids):
                valid_keys.add((
                    ex["subject_profile_id"],
                    ex["vehicle_kind_id"],
                    SvozYardDriverPlan.RowKind.EXCEPTION.value,
                ))
            if (
                sid_raw.isdigit()
                and vk_raw.isdigit()
                and rk in valid_rk
                and int(sid_raw) in yard_ids
                and (int(sid_raw), int(vk_raw), rk) in valid_keys
            ):
                SvozPlanDriverPoolAcknowledgement.objects.get_or_create(
                    plan_date=plan_date,
                    subject_profile_id=int(sid_raw),
                    vehicle_kind_id=int(vk_raw),
                    row_kind=rk,
                    defaults={"acknowledged_by": request.user},
                )
                messages.success(
                    request,
                    "Potvrzeno: pro tuto kombinaci dvůr / druh vozidla / skupina plánu může fond řidičů chybět.",
                )
            else:
                messages.error(request, "Potvrzení výjimky se nepodařilo uložit (neplatná data).")
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")

        standard_rows = _collect_plan_slots(
            request, yards, kinds_map, "drv", "vrz", "vrzn", exception_yards=set(), plan_date=plan_date
        )
        exception_pair_slots = _collect_exception_plan_by_matrix_pairs(request, yard_ids)
        exception_rows = _exception_pair_slots_as_rows(exception_pair_slots)
        dup_err = validate_plan_driver_uniqueness(
            standard_rows=standard_rows,
            exception_pair_slots=exception_pair_slots,
        )
        if dup_err:
            messages.error(request, dup_err)
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")
        v_err = validate_plan_drivers_for_vehicle_kinds(
            plan_date=plan_date,
            yard_ids=yard_ids,
            standard_rows=standard_rows,
            exception_rows=exception_rows,
        )
        if v_err:
            messages.error(request, v_err)
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")
        ratio_min_err = validate_yard_ratio_mins_from_plan_post(request.POST, yards)
        if ratio_min_err:
            messages.error(request, ratio_min_err)
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")
        save_yard_ratio_mins_from_plan_post(request.POST, yards)
        ratio_err = _validate_plan_ratios(request, yards, kinds_map, plan_date=plan_date)
        if ratio_err:
            messages.error(request, ratio_err)
            return redirect(f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}")
        replace_yard_driver_plan_for_date(
            plan_date=plan_date,
            standard_rows=standard_rows,
            exception_pair_slots=exception_pair_slots,
        )
        reconciled = reconcile_open_tasks_with_plan_for_plan_date(plan_date, actor=request.user)
        rebalanced = rebalance_standard_open_tasks_for_plan_date(plan_date, actor=request.user)
        filled, err_after_backfill = backfill_open_tasks_for_plan_date(plan_date, actor=request.user)
        auto_created, err_after_auto = auto_create_rides_for_assigned_tasks_on_date(plan_date, actor=request.user)
        merged_ride_errors = err_after_backfill + err_after_auto
        extra_parts: list[str] = []
        if reconciled:
            extra_parts.append(f"srovnáno přiřazení u {reconciled} požadavků s novým plánem")
        if rebalanced:
            extra_parts.append(f"přepočítáno přiřazení u {rebalanced} požadavků")
        if filled:
            extra_parts.append(f"doplněno přiřazení u {filled} požadavků")
        messages.success(
            request,
            f"Plán svozů na {plan_date.strftime('%d.%m.%Y')} byl uložen."
            + (f" {'; '.join(extra_parts)}." if extra_parts else ""),
        )
        if auto_created:
            messages.success(
                request,
                f"Automaticky založeno jízd z požadavků: {auto_created}.",
            )
        if merged_ride_errors:
            preview = "; ".join(merged_ride_errors[:8])
            more = ""
            if len(merged_ride_errors) > 8:
                more = f" … (+{len(merged_ride_errors) - 8} další/ích)"
            messages.warning(
                request,
                "U některých požadavků se nepodařilo automaticky založit jízdu. "
                f"Ukázka: {preview}{more}",
            )
        return redirect(
            f"{reverse('waste_docs:svoz_dispatch_plan')}?date={plan_date.isoformat()}&plan_saved=1"
        )

    eligible_by_kind: dict[int, list] = {}
    rz_eligible_by_kind: dict[int, list] = {}
    # Stejní řidiči jako dashboard panel Řidiči (bez Nepřítomnosti).
    drivers_hidden_ids = driver_ids_hidden_from_drivers_panel(plan_date)
    ex_pairs_by_yard = exception_matrix_pairs_by_yard(yard_ids)
    yard_blocks: list[dict] = []
    for y in yards:
        kind_sections: list[dict] = []
        for vk in kinds_map.get(y.pk, []):
            key = (y.pk, vk.pk)
            std_list = existing_standard.get(key, [])
            slots = []
            filled_count = len([p for p in std_list if p[0]])
            slot_weights = [
                int(std_list[i][3]) if i < len(std_list) and len(std_list[i]) > 3 else 1
                for i in range(min(filled_count, _MAX_DRIVERS_PER_YARD))
            ]
            ratio_value = ratio_label_from_weights(slot_weights[:filled_count]) if filled_count >= 2 else "1"
            ratio_is_custom = filled_count >= 2 and not is_ratio_in_presets(ratio_value, filled_count)
            open_count, tasks_preview = open_standard_tasks_preview_for_yard_kind(
                plan_date,
                subject_profile_id=y.pk,
                vehicle_kind_id=vk.pk,
            )
            ratio_min = ratio_min_containers_for_yard(getattr(y, "yard_settings", None))
            ratio_active = ratio_applies(
                filled_driver_count=filled_count,
                open_task_count=open_count,
                ratio_min=ratio_min,
            )
            ratio_hint = ""
            if ratio_active and filled_count >= 2 and open_count > 0:
                ratio_hint = effective_ratio_hint(slot_weights[:filled_count], open_count, ratio_value)
            inactive_hint = ratio_inactive_hint(
                open_task_count=open_count,
                ratio_min=ratio_min,
                filled_driver_count=filled_count,
            )
            for i in range(_MAX_DRIVERS_PER_YARD):
                if i < len(std_list):
                    did, rz_id, rz_note = std_list[i][0], std_list[i][1], std_list[i][2]
                else:
                    did, rz_id, rz_note = None, None, ""
                slots.append(
                    {
                        "index": i,
                        "driver_id": did,
                        "vehicle_rz_id": rz_id,
                        "vehicle_rz_note": rz_note,
                    }
                )
            if vk.pk not in eligible_by_kind:
                eligible_by_kind[vk.pk] = [
                    d
                    for d in driver_queryset_for_vehicle_kind(vk.pk)
                    if d.pk not in drivers_hidden_ids
                ]
            if vk.pk not in rz_eligible_by_kind:
                rz_eligible_by_kind[vk.pk] = list(vehicle_rz_queryset_for_vehicle_kind(vk.pk))
            kind_sections.append(
                {
                    "vehicle_kind": vk,
                    "slots": slots,
                    "filled_driver_count": filled_count,
                    "assignment_ratio": ratio_value,
                    "ratio_is_custom": ratio_is_custom,
                    "ratio_presets": [
                        {"value": preset, "label": preset.replace(":", " : ")}
                        for preset in ratio_presets_for_slot_count(filled_count)
                    ],
                    "ratio_slot_label": ratio_label_for_slot_count(filled_count),
                    "ratio_custom_value": RATIO_CUSTOM_VALUE,
                    "open_task_count": open_count,
                    "ratio_min_containers": ratio_min,
                    "ratio_active": ratio_active,
                    "ratio_ui_visible": filled_count >= 2,
                    "ratio_inactive_hint": inactive_hint,
                    "tasks_preview": tasks_preview,
                    "effective_ratio_hint": ratio_hint,
                    "drivers": [
                        d
                        for d in drivers_for_dispatch_plan_kind_section(
                            vk.pk,
                            [p[0] for p in std_list],
                            eligible_drivers=eligible_by_kind[vk.pk],
                        )
                        if d.pk not in drivers_hidden_ids
                    ],
                    "vehicle_rzs": vehicle_rzs_for_dispatch_plan_section(
                        vk.pk,
                        [p[1] for p in std_list],
                        eligible_rzs=rz_eligible_by_kind[vk.pk],
                    ),
                }
            )

        exception_pair_sections: list[dict] = []
        for ep in ex_pairs_by_yard.get(y.pk, []):
            pair = ep["pair"]
            vk_id = ep["vehicle_kind_id"]
            if vk_id not in eligible_by_kind:
                eligible_by_kind[vk_id] = [
                    d
                    for d in driver_queryset_for_vehicle_kind(vk_id)
                    if d.pk not in drivers_hidden_ids
                ]
            if vk_id not in rz_eligible_by_kind:
                rz_eligible_by_kind[vk_id] = list(vehicle_rz_queryset_for_vehicle_kind(vk_id))
            did, rz_id, rz_note = plan_assignment_for_exception_pair(pair, existing_exception)
            assigned_drivers = [did] if did else []
            assigned_rzs = [rz_id] if rz_id else []
            exception_pair_sections.append(
                {
                    "pair_id": ep["pair_id"],
                    "label": ep["label"],
                    "slot": ep["slot"],
                    "vehicle_kind": ep["vehicle_kind"],
                    "vehicle_kind_id": vk_id,
                    "driver_id": did,
                    "vehicle_rz_id": rz_id,
                    "vehicle_rz_note": rz_note,
                    "tasks_preview": open_tasks_preview_for_matrix_pair(plan_date, pair),
                    "drivers": [
                        d
                        for d in drivers_for_dispatch_plan_kind_section(
                            vk_id,
                            assigned_drivers,
                            eligible_drivers=eligible_by_kind[vk_id],
                        )
                        if d.pk not in drivers_hidden_ids
                    ],
                    "vehicle_rzs": vehicle_rzs_for_dispatch_plan_section(
                        vk_id,
                        assigned_rzs,
                        eligible_rzs=rz_eligible_by_kind[vk_id],
                    ),
                }
            )

        kind_section_vk_ids = [int(section["vehicle_kind"].pk) for section in kind_sections]
        exception_groups = group_exception_sections_by_vehicle_kind(
            exception_pair_sections,
            kind_section_vk_ids=kind_section_vk_ids,
        )
        exception_badge_summary = (
            exception_plan_badge_summary(
                exception_pair_sections,
                kind_section_vk_ids=kind_section_vk_ids,
            )
            if exception_pair_sections
            else ""
        )

        yard_blocks.append(
            {
                "yard": y,
                "ratio_min_containers": ratio_min_containers_for_yard(getattr(y, "yard_settings", None)),
                "kind_sections": kind_sections,
                "exception_pair_sections": exception_pair_sections,
                "exception_groups": exception_groups,
                "exception_badge_summary": exception_badge_summary,
            }
        )

    plan_gap_items = plan_coverage_gap_items(plan_date, yard_ids)
    plan_pool_acks = list(
        SvozPlanDriverPoolAcknowledgement.objects.filter(
            plan_date=plan_date,
            subject_profile_id__in=yard_ids,
        )
        .select_related("subject_profile", "vehicle_kind", "acknowledged_by")
        .order_by("subject_profile__company_name", "vehicle_kind__sort_order", "vehicle_kind__name", "row_kind")
    )

    plan_rz_has_ride_ids = vehicle_rz_ids_with_pruvodka_on_date(plan_date, user=request.user)
    plan_rz_multi_slot_ids = vehicle_rz_ids_multi_assigned_in_plan(plan_date)

    return render(
        request,
        "waste_docs/svoz_dispatch_plan.html",
        {
            "plan_date": plan_date,
            "yard_blocks": yard_blocks,
            "plan_gap_items": plan_gap_items,
            "plan_pool_acks": plan_pool_acks,
            "plan_rz_has_ride_ids": plan_rz_has_ride_ids,
            "plan_rz_multi_slot_ids": plan_rz_multi_slot_ids,
            "svoz_ratio_config": build_svoz_ratio_client_config(),
        },
    )
