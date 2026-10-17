"""Náhled otevřených požadavků běžného svozu (B1–B4) pro plán."""

from __future__ import annotations

from django.db.models import Q

from waste_docs.models import SvozTask


def open_standard_tasks_preview_for_yard_kind(
    plan_date,
    *,
    subject_profile_id: int,
    vehicle_kind_id: int,
) -> tuple[int, list[str]]:
    """
    Otevřené požadavky běžného svozu pro dvůr a druh vozidla.
    Vrací (počet, řádky pro zobrazení).
    """
    lines: list[str] = []
    qs = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            subject_profile_id=subject_profile_id,
            vehicle_kind_id=vehicle_kind_id,
        )
        .filter(
            Q(source_waste_suffix_pair__yard_svoz_auto_assign_driver=True)
            | Q(
                source_waste_suffix_pair__isnull=True,
            )
        )
        .select_related("source_waste_suffix_pair")
        .only(
            "pk",
            "container_numbers",
            "matrix_display_label",
            "source_waste_suffix_pair__yard_svoz_auto_assign_driver",
        )
        .order_by("pk")
    )
    for task in qs:
        pair = task.source_waste_suffix_pair
        if pair is not None and not pair.yard_svoz_auto_assign_driver:
            continue
        num = (task.container_numbers or "").strip()
        label = (task.matrix_display_label or "").strip()
        if num and label:
            lines.append(f"{label}: {num}")
        elif num:
            lines.append(num)
        elif label:
            lines.append(label)
        else:
            lines.append(f"úkol #{task.pk}")
    return len(lines), lines
