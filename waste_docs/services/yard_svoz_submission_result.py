"""Text výsledku odeslání řádku matice (řidič / požadavek / hazard) — jen čtení po submitu."""

from __future__ import annotations

from waste_docs.models import SvozTask

RESULT_UNASSIGNED = "Požadavek na svoz bez řidiče (dashboard)"
RESULT_HAZARD = "Nebezpečný odpad — fronta dispečera"


def _driver_label(driver) -> str:
    full = " ".join(
        part for part in [(driver.first_name or "").strip(), (driver.last_name or "").strip()] if part
    )
    return full or str(driver)


def result_summary_for_svoz_task(*, task: SvozTask, ride_warning: str | None = None) -> str:
    driver = getattr(task, "assigned_driver", None)
    if driver is None:
        return RESULT_UNASSIGNED
    parts = [f"Řidič: {_driver_label(driver)}"]
    rz = getattr(task, "assigned_vehicle_rz", None)
    if rz is not None:
        rz_text = (getattr(rz, "value", None) or str(rz)).strip()
        if rz_text:
            parts.append(f"RZ {rz_text}")
    if getattr(task, "resolved_pruvodka_id", None):
        parts.append("jízda založena")
    elif ride_warning:
        parts.append("jízda nezaložena")
    return " · ".join(parts)


def result_summary_for_hazard() -> str:
    return RESULT_HAZARD
