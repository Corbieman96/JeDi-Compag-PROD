"""Celočíselné kvóty z poměru řidičů B1–B4 pro plán svozů."""

from __future__ import annotations

MAX_ASSIGNMENT_WEIGHT = 9
RATIO_CUSTOM_VALUE = "__custom__"

ASSIGNMENT_RATIO_CHOICES: dict[str, tuple[int, int]] = {
    "1:1": (1, 1),
    "1:2": (1, 2),
    "1:3": (1, 3),
    "2:1": (2, 1),
    "3:1": (3, 1),
    "3:2": (3, 2),
}

RATIO_PRESETS_2: list[str] = list(ASSIGNMENT_RATIO_CHOICES.keys())

RATIO_PRESETS_3: list[str] = [
    "1:1:1",
    "2:1:1",
    "1:2:1",
    "1:1:2",
    "2:2:1",
    "5:2:1",
    "1:2:3",
    "3:2:1",
]

RATIO_PRESETS_4: list[str] = [
    "1:1:1:1",
    "2:1:1:1",
    "3:2:1:1",
    "1:2:3:4",
    "2:2:1:1",
]


def ratio_presets_for_slot_count(slot_count: int) -> list[str]:
    if slot_count == 2:
        return RATIO_PRESETS_2[:]
    if slot_count == 3:
        return RATIO_PRESETS_3[:]
    if slot_count >= 4:
        return RATIO_PRESETS_4[:]
    return []


def ratio_label_for_slot_count(slot_count: int) -> str:
    if slot_count <= 1:
        return ""
    parts = [f"B{i + 1}" for i in range(min(slot_count, 4))]
    return " : ".join(parts)


def parse_ratio_parts(ratio: str) -> list[int]:
    parts: list[int] = []
    for chunk in (ratio or "").split(":"):
        text = chunk.strip()
        if not text.isdigit():
            continue
        value = int(text)
        if value < 1:
            continue
        parts.append(value)
    return parts


def ratio_label_from_weights(weights: list[int]) -> str:
    if not weights:
        return "1:1"
    return ":".join(str(max(1, int(w or 1))) for w in weights)


def ratio_value_from_weights(w1: int, w2: int) -> str:
    for label, pair in ASSIGNMENT_RATIO_CHOICES.items():
        if pair == (w1, w2):
            return label
    return f"{max(1, w1)}:{max(1, w2)}"


def default_ratio_for_slot_count(slot_count: int) -> str:
    if slot_count < 2:
        return "1"
    return ":".join(["1"] * slot_count)


def validate_ratio_for_slots(ratio: str, slot_count: int) -> str | None:
    if slot_count < 2:
        return None
    parts = parse_ratio_parts(ratio)
    if len(parts) != slot_count:
        return (
            f"Poměr musí mít {slot_count} čísel oddělených dvojtečkou "
            f"(např. {default_ratio_for_slot_count(slot_count)})."
        )
    if any(part > MAX_ASSIGNMENT_WEIGHT for part in parts):
        return f"Každá část poměru smí být nejvýše {MAX_ASSIGNMENT_WEIGHT}."
    if any(part < 1 for part in parts):
        return "Každá část poměru musí být kladné celé číslo."
    return None


def resolve_ratio_from_post(ratio_raw: str, ratio_custom: str, slot_count: int) -> str:
    if slot_count < 2:
        return default_ratio_for_slot_count(max(slot_count, 0))
    raw = (ratio_raw or "").strip()
    if raw == RATIO_CUSTOM_VALUE:
        custom = (ratio_custom or "").strip()
        return custom or default_ratio_for_slot_count(slot_count)
    if raw:
        return raw
    return default_ratio_for_slot_count(slot_count)


def weights_for_ratio(ratio: str, slot_count: int) -> list[int]:
    if slot_count <= 0:
        return []
    if slot_count == 1:
        return [1]

    parts = parse_ratio_parts(ratio)
    if len(parts) == slot_count:
        return [max(1, min(MAX_ASSIGNMENT_WEIGHT, int(p))) for p in parts]

    if slot_count == 2:
        w1, w2 = ASSIGNMENT_RATIO_CHOICES.get((ratio or "").strip(), (1, 1))
        return [w1, w2]

    return [1] * slot_count


def effective_integer_quotas(weights: list[int], total_tasks: int) -> list[int]:
    """
    Rozdělí total_tasks mezi sloty podle vah (metoda největších zbytků).
    Při rozdělování zbytku upřednostní vyšší váhu, pak pořadí slotu.
    """
    n = len(weights)
    if n == 0 or total_tasks <= 0:
        return [0] * n
    safe_weights = [max(1, int(w or 1)) for w in weights]
    weight_sum = sum(safe_weights)
    if weight_sum <= 0:
        return [0] * n

    raw = [total_tasks * w / weight_sum for w in safe_weights]
    floors = [int(x) for x in raw]
    quotas = floors[:]
    remainder = total_tasks - sum(quotas)
    if remainder <= 0:
        return quotas

    fractions = [
        (raw[i] - floors[i], -safe_weights[i], i)
        for i in range(n)
    ]
    fractions.sort(reverse=True)
    for _, _, idx in fractions[:remainder]:
        quotas[idx] += 1
    return quotas


def effective_ratio_label(weights: list[int], total_tasks: int) -> str:
    quotas = effective_integer_quotas(weights, total_tasks)
    if not quotas:
        return "0"
    if len(quotas) == 1:
        return str(quotas[0])
    return ":".join(str(q) for q in quotas)


def effective_ratio_hint(weights: list[int], total_tasks: int, ratio_label: str) -> str:
    if total_tasks <= 0 or len(weights) < 2:
        return ""
    effective = effective_ratio_label(weights, total_tasks)
    effective_display = effective.replace(":", " : ")
    if effective == ratio_label:
        return f"Dnes {total_tasks} kontejnerů → rozdělení {effective_display}"
    ratio_display = ratio_label.replace(":", " : ")
    return (
        f"Dnes {total_tasks} kontejnerů → rozdělení {effective_display} "
        f"(z poměru {ratio_display})"
    )


def is_ratio_in_presets(ratio_label: str, slot_count: int) -> bool:
    presets = ratio_presets_for_slot_count(slot_count)
    return ratio_label in presets


def build_svoz_ratio_client_config() -> dict:
    """JSON pro klienta plánu svozů — dynamické presety poměru B1–B4."""
    return {
        "customValue": RATIO_CUSTOM_VALUE,
        "presets": {
            "2": ratio_presets_for_slot_count(2),
            "3": ratio_presets_for_slot_count(3),
            "4": ratio_presets_for_slot_count(4),
        },
        "defaults": {
            "2": default_ratio_for_slot_count(2),
            "3": default_ratio_for_slot_count(3),
            "4": default_ratio_for_slot_count(4),
        },
        "slotLabels": {
            "2": ratio_label_for_slot_count(2),
            "3": ratio_label_for_slot_count(3),
            "4": ratio_label_for_slot_count(4),
        },
    }
