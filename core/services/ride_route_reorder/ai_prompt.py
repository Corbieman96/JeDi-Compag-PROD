"""Sestavení textu promptu pro externí AI — optimalizace pořadí zastávek."""

from __future__ import annotations

from waste_docs.models import Pruvodka
from waste_docs.services.ride_print_order import sort_rides_list

from .ai_prompt_glossary import (
    AI_TASK_LINES,
    GLOSSARY_LINES,
    OUTPUT_FORMAT_LINES,
    PROMPT_EXAMPLE_LINES,
    ROUTING_PRIORITY_LINES,
    build_activity_summary_lines,
)
from .container_labels import format_ride_containers_for_prompt, load_passport_map
from .stop_duration_estimate import (
    build_follow_up_pair_summary,
    estimate_stop_duration,
    format_follow_up_link,
    format_stop_duration_for_prompt,
    load_activity_minutes_by_name,
    load_activity_minutes_for_rides,
    prepare_follow_up_maps,
)


def _format_ride_line_for_ai(ride: Pruvodka) -> str:
    """Čitelný řádek zastávky pro AI (podobně jako v zadání dispečinku)."""
    subject = (ride.name_snapshot or "").strip() or "—"
    activity = (ride.activity_snapshot or "").strip() or "—"
    address = (ride.address_snapshot or "").strip() or "—"
    waste = (ride.waste_type_snapshot or "").strip() or "—"
    suffix = (ride.suffix_snapshot or "").strip() or "—"
    note = (ride.contact_note or "").strip()
    parts = [f"#{ride.pk} {subject}", activity, address, waste, suffix]
    line = " | ".join(parts)
    if note:
        line += f" | poznámka: {note}"
    return line


def build_ride_group_ai_prompt(
    *,
    drive_date,
    vehicle_rz: str,
    driver_label: str,
    items: list[Pruvodka],
) -> str:
    ordered = sort_rides_list(list(items))
    container_numbers: set[str] = set()
    for ride in ordered:
        for num in [(ride.container_number or "").strip(), (ride.container_number_2 or "").strip()]:
            if num:
                container_numbers.add(num)
    passport_map = load_passport_map(container_numbers)
    activity_minutes = load_activity_minutes_for_rides(ordered)
    minutes_by_name = load_activity_minutes_by_name()

    activity_names = [(ride.activity_snapshot or "").strip() for ride in ordered]
    activity_summary = build_activity_summary_lines(activity_names)
    follow_up_summary = build_follow_up_pair_summary(ordered)
    rides_by_pk, children_by_parent = prepare_follow_up_maps(ordered)

    lines = [
        *AI_TASK_LINES,
        "",
        *GLOSSARY_LINES,
        "",
        *ROUTING_PRIORITY_LINES,
        "",
        *PROMPT_EXAMPLE_LINES,
        "",
    ]
    if activity_summary:
        lines.extend(activity_summary)
        lines.append("")
    if follow_up_summary:
        lines.extend(follow_up_summary)
        lines.append("")
    lines.extend(
        [
            f"Datum jízdy: {drive_date.strftime('%d.%m.%Y')}",
            f"RZ vozidla: {vehicle_rz or '—'}",
            f"Řidič: {driver_label or '—'}",
            f"Počet zastávek: {len(ordered)}",
            "",
            "Vstupní data — zastávky této trasy (použij pouze tato pk):",
            "",
        ]
    )
    for ride in ordered:
        lines.append(_format_ride_line_for_ai(ride))

    lines.extend(
        [
            "",
            "Detailní tabulka (pk | SND | subjekt | činnost | adresa | odpad | koncovka | "
            "kontejner(y) | poznámka | odhad min | návaznost):",
            "",
        ]
    )
    for ride in ordered:
        snd = (ride.snd_cislo_listu or "").strip() or "—"
        subject = (ride.name_snapshot or "").strip() or "—"
        activity = (ride.activity_snapshot or "").strip() or "—"
        address = (ride.address_snapshot or "").strip() or "—"
        waste = (ride.waste_type_snapshot or "").strip() or "—"
        suffix = (ride.suffix_snapshot or "").strip() or "—"
        containers = format_ride_containers_for_prompt(ride, passport_map)
        note = (ride.contact_note or "").strip() or "—"
        duration = format_stop_duration_for_prompt(
            estimate_stop_duration(
                ride,
                passport_map,
                activity_minutes=activity_minutes,
                minutes_by_name=minutes_by_name,
            )
        )
        follow_up = format_follow_up_link(
            ride,
            rides_by_pk=rides_by_pk,
            children_by_parent=children_by_parent,
        )
        lines.append(
            f"{ride.pk}\t{snd}\t{subject}\t{activity}\t{address}\t{waste}\t{suffix}\t"
            f"{containers}\t{note}\t{duration}\t{follow_up}"
        )

    lines.append("")
    lines.extend(OUTPUT_FORMAT_LINES)
    return "\n".join(lines)
