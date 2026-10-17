"""Mapování výjimkových řádků matice na sloty V1–V4 v plánu svozů."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from catalogs.models import NameSubjectWasteSuffixPair

SLOT_MIN = 1
SLOT_MAX = 4


def plan_sort_order_from_slot(slot: int) -> int:
    """V1 → 0, V4 → 3 (sort_order na SvozYardDriverPlan)."""
    return int(slot) - 1


def exception_slot_for_pair(pair: NameSubjectWasteSuffixPair) -> int | None:
    """Číslo slotu 1–4 u výjimky, jinak None."""
    if pair.yard_svoz_auto_assign_driver:
        return None
    slot = getattr(pair, "yard_svoz_exception_slot", None)
    if slot is None:
        return None
    try:
        n = int(slot)
    except (TypeError, ValueError):
        return None
    if SLOT_MIN <= n <= SLOT_MAX:
        return n
    return None


def matrix_pair_display_label(pair: NameSubjectWasteSuffixPair) -> str:
    label = (pair.yard_svoz_display_label or "").strip()
    if label:
        return label
    wt = getattr(pair, "waste_type", None)
    suf = getattr(pair, "suffix", None)
    parts = []
    if wt:
        parts.append(str(wt))
    if suf:
        parts.append(str(suf.value if hasattr(suf, "value") else suf))
    return " — ".join(parts) if parts else f"řádek #{pair.pk}"


def exception_pairs_by_yard_slot(
    yard_ids: list[int],
) -> dict[tuple[int, int, int], list[NameSubjectWasteSuffixPair]]:
    """
    (subject_profile_id, yard_vehicle_kind_id, slot 1–4) → seznam výjimkových párů.
  """
    if not yard_ids:
        return {}
    out: dict[tuple[int, int, int], list[NameSubjectWasteSuffixPair]] = {}
    qs = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id__in=yard_ids,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind_id__isnull=False,
            yard_svoz_exception_slot__isnull=False,
        )
        .select_related("waste_type", "suffix", "yard_vehicle_kind")
        .order_by("sort_order", "id")
    )
    for pair in qs:
        slot = exception_slot_for_pair(pair)
        if slot is None or pair.yard_vehicle_kind_id is None:
            continue
        key = (pair.subject_profile_id, int(pair.yard_vehicle_kind_id), slot)
        out.setdefault(key, []).append(pair)
    return out


def exception_slot_labels_for_plan(
    yard_ids: list[int],
) -> dict[tuple[int, int, int], str]:
    """(yard_id, vehicle_kind_id, slot 1–4) → text řádků matice pro hlavičku V-slots."""
    by_key = exception_pairs_by_yard_slot(yard_ids)
    out: dict[tuple[int, int, int], str] = {}
    for key, pairs in by_key.items():
        labels = [matrix_pair_display_label(p) for p in pairs]
        out[key] = "; ".join(labels)
    return out


def exception_matrix_pairs_by_yard(yard_ids: list[int]) -> dict[int, list[dict]]:
    """Sběrný dvůr → výjimkové řádky matice (jen s platným slotem V1–V4)."""
    if not yard_ids:
        return {}
    from collections import defaultdict

    out: dict[int, list[dict]] = defaultdict(list)
    qs = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile_id__in=yard_ids,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind_id__isnull=False,
        )
        .select_related("waste_type", "suffix", "yard_vehicle_kind")
        .order_by("yard_svoz_exception_slot", "sort_order", "id")
    )
    for pair in qs:
        slot = exception_slot_for_pair(pair)
        if slot is None:
            continue
        out[pair.subject_profile_id].append(
            {
                "pair": pair,
                "pair_id": pair.pk,
                "label": matrix_pair_display_label(pair),
                "slot": slot,
                "vehicle_kind": pair.yard_vehicle_kind,
                "vehicle_kind_id": pair.yard_vehicle_kind_id,
            }
        )
    return dict(out)


def _vehicle_kind_short_label(section: dict[str, Any]) -> str:
    vk = section.get("vehicle_kind")
    if vk is None:
        return "?"
    shortcut = (getattr(vk, "shortcut", None) or "").strip()
    if shortcut:
        return shortcut
    display = getattr(vk, "display_label", None)
    if callable(display):
        return display()
    return str(vk)


def _exception_group_labels_text(sections: list[dict[str, Any]]) -> str:
    counts = Counter((s.get("label") or "").strip() or "řádek" for s in sections)
    parts: list[str] = []
    for label, count in sorted(counts.items(), key=lambda item: item[0].casefold()):
        if count > 1:
            parts.append(f"{count}× {label}")
        else:
            parts.append(label)
    return ", ".join(parts)


def group_exception_sections_by_vehicle_kind(
    exception_sections: list[dict[str, Any]],
    *,
    kind_section_vk_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Výjimkové řádky seskupené podle druhu vozidla.

    Pořadí skupin: nejdřív druhy z běžného svozu (kind_sections), pak zbytek
  (např. 3H jen ve výjimkách bez bloku B1–B4) — zobrazí se vedle předchozí skupiny.
    """
    if not exception_sections:
        return []
    by_vk: dict[int, list[dict[str, Any]]] = defaultdict(list)
    vk_meta: dict[int, Any] = {}
    for section in exception_sections:
        vk_id = int(section["vehicle_kind_id"])
        by_vk[vk_id].append(section)
        if vk_id not in vk_meta:
            vk_meta[vk_id] = section.get("vehicle_kind")

    ordered_ids: list[int] = []
    seen: set[int] = set()
    for vk_id in kind_section_vk_ids or []:
        if vk_id in by_vk and vk_id not in seen:
            ordered_ids.append(vk_id)
            seen.add(vk_id)
    for vk_id in sorted(
        by_vk.keys(),
        key=lambda i: (
            getattr(vk_meta.get(i), "sort_order", 0),
            getattr(vk_meta.get(i), "name", ""),
            i,
        ),
    ):
        if vk_id not in seen:
            ordered_ids.append(vk_id)

    groups: list[dict[str, Any]] = []
    for vk_id in ordered_ids:
        sections = by_vk[vk_id]
        vk = vk_meta.get(vk_id) or (sections[0].get("vehicle_kind") if sections else None)
        title = f"{vk.display_label()} — výjimky" if vk else "Výjimky"
        groups.append(
            {
                "vehicle_kind_id": vk_id,
                "vehicle_kind": vk,
                "group_title": title,
                "sections": sections,
            }
        )
    return groups


def exception_plan_badge_summary(
    exception_sections: list[dict[str, Any]],
    *,
    kind_section_vk_ids: list[int] | None = None,
) -> str:
    """Text do badge hlavičky dvora — ne počet „výjimkových řádků matice“."""
    groups = group_exception_sections_by_vehicle_kind(
        exception_sections,
        kind_section_vk_ids=kind_section_vk_ids,
    )
    if not groups:
        return ""
    parts: list[str] = []
    for group in groups:
        sections = group["sections"]
        if not sections:
            continue
        vk_short = _vehicle_kind_short_label(sections[0])
        parts.append(f"{vk_short} ({_exception_group_labels_text(sections)})")
    if not parts:
        return ""
    return "Běžný svoz + výjimky: " + ", ".join(parts)


def plan_assignment_for_exception_pair(
    pair: NameSubjectWasteSuffixPair,
    existing_exception: dict[
        tuple[int, int | None],
        dict[int, tuple[int, int | None, str] | tuple[int, int | None, str, int]],
    ],
) -> tuple[int | None, int | None, str]:
    """Načte uložený plán pro daný výjimkový řádek matice (podle slotu V / sort_order)."""
    if pair.yard_vehicle_kind_id is None:
        return None, None, ""
    slot = exception_slot_for_pair(pair)
    if slot is None:
        return None, None, ""
    key = (pair.subject_profile_id, pair.yard_vehicle_kind_id)
    sort_order = plan_sort_order_from_slot(slot)
    raw = existing_exception.get(key, {}).get(sort_order, (None, None, ""))
    return raw[0], raw[1], (raw[2] or "") if len(raw) > 2 else ""


def open_tasks_preview_for_matrix_pair(
    plan_date,
    pair: NameSubjectWasteSuffixPair,
) -> list[str]:
    """Kontejnery z otevřených úkolů pro konkrétní řádek matice."""
    from django.db.models import Q

    from waste_docs.models import SvozTask

    lines: list[str] = []
    for task in SvozTask.objects.filter(
        target_date=plan_date,
        status=SvozTask.Status.OPEN,
        subject_profile_id=pair.subject_profile_id,
    ).filter(
        Q(source_waste_suffix_pair_id=pair.pk)
        | Q(
            source_waste_suffix_pair__isnull=True,
            waste_type_id=pair.waste_type_id,
            suffix_id=pair.suffix_id,
        )
    ).only("pk", "container_numbers", "matrix_display_label"):
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
    return lines


def open_tasks_preview_by_exception_slot(
    plan_date,
    yard_ids: list[int],
) -> dict[tuple[int, int, int], list[str]]:
    """(yard_id, vehicle_kind_id, slot) → seznam textů kontejnerů z otevřených úkolů."""
    from waste_docs.models import SvozTask

    if not yard_ids:
        return {}
    out: dict[tuple[int, int, int], list[str]] = {}
    tasks = (
        SvozTask.objects.filter(
            target_date=plan_date,
            status=SvozTask.Status.OPEN,
            subject_profile_id__in=yard_ids,
        )
        .select_related("source_waste_suffix_pair")
        .only(
            "pk",
            "subject_profile_id",
            "vehicle_kind_id",
            "container_numbers",
            "matrix_display_label",
            "source_waste_suffix_pair_id",
            "source_waste_suffix_pair__yard_svoz_exception_slot",
            "source_waste_suffix_pair__yard_svoz_auto_assign_driver",
            "source_waste_suffix_pair__yard_vehicle_kind_id",
        )
    )
    for task in tasks:
        pair = task.source_waste_suffix_pair
        if not pair:
            continue
        slot = exception_slot_for_pair(pair)
        if slot is None:
            continue
        vk_id = pair.yard_vehicle_kind_id or task.vehicle_kind_id
        if not vk_id:
            continue
        key = (task.subject_profile_id, int(vk_id), slot)
        num = (task.container_numbers or "").strip()
        label = (task.matrix_display_label or "").strip()
        if num and label:
            line = f"{label}: {num}"
        elif num:
            line = num
        elif label:
            line = label
        else:
            line = f"úkol #{task.pk}"
        out.setdefault(key, []).append(line)
    return out
