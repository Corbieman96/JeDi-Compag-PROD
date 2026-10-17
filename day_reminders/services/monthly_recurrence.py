"""Měsíční opakování poznámek — N-tý den v týdnu v měsíci."""

from __future__ import annotations

import calendar
from datetime import date

_WEEKDAY_LABELS = {
    0: "pondělí",
    1: "úterý",
    2: "středa",
    3: "čtvrtek",
    4: "pátek",
    5: "sobota",
    6: "neděle",
}

_ORDINAL_LABELS = {
    1: "1.",
    2: "2.",
    3: "3.",
    4: "4.",
    -1: "poslední",
}


def normalize_monthly_rule(raw: dict | None) -> dict:
    if not raw or not isinstance(raw, dict):
        raise ValueError("Chybí měsíční pravidlo opakování.")
    try:
        ordinal = int(raw.get("ordinal"))
        weekday = int(raw.get("weekday"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Neplatné měsíční pravidlo opakování.") from exc
    if ordinal not in {1, 2, 3, 4, -1}:
        raise ValueError("Pořadí v měsíci musí být 1–4 nebo poslední.")
    if not 0 <= weekday <= 6:
        raise ValueError("Neplatný den v týdnu.")
    return {"ordinal": ordinal, "weekday": weekday}


def parse_monthly_rule_from_post(post) -> dict:
    try:
        ordinal = int((post.get("repeat_monthly_ordinal") or "").strip())
        weekday = int((post.get("repeat_monthly_weekday") or "").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Vyberte pořadí a den v týdnu pro měsíční opakování.") from exc
    return normalize_monthly_rule({"ordinal": ordinal, "weekday": weekday})


def nth_weekday_in_month(year: int, month: int, weekday: int, ordinal: int) -> date | None:
    """Vrátí datum N-tého weekday v měsíci, nebo None pokud neexistuje."""
    if ordinal == -1:
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day)
        while d.weekday() != weekday:
            d = d.replace(day=d.day - 1)
        return d

    count = 0
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        d = date(year, month, day)
        if d.weekday() == weekday:
            count += 1
            if count == ordinal:
                return d
    return None


def monthly_occurrence_date(rule: dict, year: int, month: int) -> date | None:
    normalized = normalize_monthly_rule(rule)
    return nth_weekday_in_month(year, month, normalized["weekday"], normalized["ordinal"])


def monthly_matches_date(rule: dict | None, d: date) -> bool:
    if not rule:
        return False
    occurrence = monthly_occurrence_date(rule, d.year, d.month)
    return occurrence == d


def monthly_display(rule: dict | None) -> str:
    if not rule:
        return ""
    try:
        normalized = normalize_monthly_rule(rule)
    except ValueError:
        return ""
    weekday_label = _WEEKDAY_LABELS.get(normalized["weekday"], "?")
    ordinal = normalized["ordinal"]
    if ordinal == -1:
        return f"Poslední {weekday_label.lower()} v měsíci"
    ordinal_label = _ORDINAL_LABELS.get(ordinal, f"{ordinal}.")
    return f"Každý {ordinal_label} {weekday_label.lower()} v měsíci"
