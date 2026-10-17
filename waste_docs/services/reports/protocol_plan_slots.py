"""Sloty plánu svozů pro denní protokol — řidič+RZ bez průvodky."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from core.services.dashboard_rides import org_occupied_rz_driver_pairs
from waste_docs.models import SvozTask
from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import planned_svoz_vehicle_groups
from waste_docs.svoz_prefill import build_svoz_task_prefill_bundle


@dataclass(frozen=True)
class ProtocolPlanSlot:
    driver_id: int
    driver_last_name: str
    vehicle_rz_id: int
    vehicle_rz: str
    drive_date: date
    lines: tuple[dict, ...]


def _line_dict_from_svoz_task(task: SvozTask) -> dict:
    from waste_docs.activity_fields import activity_uses_fulfillment_address
    from waste_docs.services.reports.protocol_note_overflow import protocol_note_for_cell

    bundle = build_svoz_task_prefill_bundle(task)
    ini = bundle.get("initial") or {}
    sub = task.subject_profile
    subject_name = (getattr(sub, "company_name", None) or "").strip()
    if not subject_name and sub and getattr(sub, "name", None):
        subject_name = (sub.name.value or "").strip()

    activity_id = task.activity_id
    activity_label = ""
    if task.activity_id and task.activity:
        activity_label = (task.activity.name or "").strip()
    matrix_label = (task.matrix_display_label or "").strip()
    if matrix_label and not activity_label:
        activity_label = matrix_label

    note_raw = (ini.get("contact_note") or "").strip()
    note_cell, _needs_supplement = protocol_note_for_cell(note_raw)
    uses_address = activity_uses_fulfillment_address(activity_id)

    waste_type_label = ""
    if task.waste_type_id and task.waste_type:
        waste_type_label = (task.waste_type.value or "").strip()
    suffix_label = ""
    if task.suffix_id and task.suffix:
        suffix_label = (task.suffix.value or "").strip()

    return {
        "snd_cislo_listu": "",
        "activity_snapshot": activity_label,
        "name_snapshot": subject_name,
        "address_snapshot": (ini.get("fulfillment_address_value") or "").strip(),
        "suppress_kde": not uses_address,
        "waste_type_snapshot": waste_type_label,
        "suffix_snapshot": suffix_label,
        "waste_code_snapshot": (ini.get("waste_code_display") or "").strip(),
        "waste_category_snapshot": (ini.get("waste_category_display") or "").strip(),
        "container_number": (ini.get("container_number") or "").strip(),
        "contract_number_snapshot": (ini.get("contract_number") or "").strip(),
        "contact_note": note_cell,
        "contact_phone": (ini.get("contact_phone") or "").strip(),
        "container_number_2": (ini.get("container_number_2") or "").strip(),
    }


def _open_tasks_for_plan_slot(plan_date: date, driver_id: int, vehicle_rz_id: int) -> list[SvozTask]:
    return list(
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            assigned_driver_id=driver_id,
            assigned_vehicle_rz_id=vehicle_rz_id,
            resolved_pruvodka__isnull=True,
        )
        .select_related(
            "subject_profile",
            "subject_profile__name",
            "waste_type",
            "suffix",
            "activity",
        )
        .order_by("pk")
    )


def plan_only_protocol_slots(plan_date: date) -> list[ProtocolPlanSlot]:
    """Řidič+RZ z plánu bez existující průvodky; řádky z otevřených přiřazených úkolů."""
    groups = planned_svoz_vehicle_groups(plan_date, org_occupied_rz_driver_pairs(plan_date))
    slots: list[ProtocolPlanSlot] = []
    for group in groups:
        driver_id = int(group.get("driver_id") or 0)
        rz_id = int(group.get("vehicle_rz_id") or 0)
        if not driver_id or not rz_id:
            continue
        tasks = _open_tasks_for_plan_slot(plan_date, driver_id, rz_id)
        lines = tuple(_line_dict_from_svoz_task(task) for task in tasks)
        driver_last_name = (group.get("driver_last_name") or "—").strip() or "—"
        rz_label = (group.get("vehicle_rz") or "").strip() or "—"
        slots.append(
            ProtocolPlanSlot(
                driver_id=driver_id,
                driver_last_name=driver_last_name,
                vehicle_rz_id=rz_id,
                vehicle_rz=rz_label,
                drive_date=plan_date,
                lines=lines,
            )
        )
    slots.sort(key=lambda s: (s.vehicle_rz.lower(), s.driver_last_name.lower()))
    return slots


def plan_slots_signature(plan_date: date) -> tuple:
    """Otisk obsahu plan-only slotů pro detekci změny protokolu."""
    parts: list[tuple] = []
    for slot in plan_only_protocol_slots(plan_date):
        line_sig = tuple(
            (
                line.get("name_snapshot"),
                line.get("waste_type_snapshot"),
                line.get("suffix_snapshot"),
                line.get("container_number"),
                line.get("contact_note"),
            )
            for line in slot.lines
        )
        parts.append((slot.driver_id, slot.vehicle_rz_id, line_sig))
    return tuple(parts)


def plan_tasks_changed_since(plan_date: date, since_ts: float) -> bool:
    """True pokud po vygenerování protokolu přibyly/přiřazeny úkoly pro plan-only sloty."""
    for slot in plan_only_protocol_slots(plan_date):
        latest = (
            SvozTask.objects.filter(
                target_date=plan_date,
                status=SvozTask.Status.OPEN,
                assigned_driver_id=slot.driver_id,
                assigned_vehicle_rz_id=slot.vehicle_rz_id,
                resolved_pruvodka__isnull=True,
            )
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )
        if latest and latest.timestamp() > since_ts:
            return True
    return False
