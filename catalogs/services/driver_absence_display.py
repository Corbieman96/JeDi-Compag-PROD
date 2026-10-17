"""Zobrazení kalendářové nepřítomnosti řidiče (stránka úpravy profilu)."""

from __future__ import annotations

from datetime import date

from catalogs.models import DriverAbsence

_CHIP_CLASS_BY_TYPE: dict[str, str] = {
    DriverAbsence.AbsenceType.VACATION: "driver-absence-chip--vacation",
    DriverAbsence.AbsenceType.SICK: "driver-absence-chip--sick",
    DriverAbsence.AbsenceType.DOCTOR: "driver-absence-chip--doctor",
    DriverAbsence.AbsenceType.GARBAGE: "driver-absence-chip--garbage",
    DriverAbsence.AbsenceType.TRAINING: "driver-absence-chip--training",
    DriverAbsence.AbsenceType.OBSTACLE: "driver-absence-chip--obstacle",
    DriverAbsence.AbsenceType.COMPENSATORY_LEAVE: "driver-absence-chip--leave",
    DriverAbsence.AbsenceType.UNPAID_LEAVE: "driver-absence-chip--unpaid",
    DriverAbsence.AbsenceType.WEDDING: "driver-absence-chip--event",
    DriverAbsence.AbsenceType.FUNERAL: "driver-absence-chip--event",
    DriverAbsence.AbsenceType.PATERNITY: "driver-absence-chip--parental",
    DriverAbsence.AbsenceType.MATERNITY_PARENTAL: "driver-absence-chip--parental",
    DriverAbsence.AbsenceType.BLOOD_DONOR: "driver-absence-chip--other",
    DriverAbsence.AbsenceType.OCR: "driver-absence-chip--parental",
    DriverAbsence.AbsenceType.OTHER: "driver-absence-chip--other",
}


def format_absence_date_range(date_from: date, date_to: date) -> str:
    """Jednotný formát období (stejná logika jako dashboard)."""
    if date_from == date_to:
        return date_from.strftime("%d.%m.%Y")
    if date_from.year == date_to.year:
        return f"{date_from.strftime('%d.%m.')}–{date_to.strftime('%d.%m.%Y')}"
    return f"{date_from.strftime('%d.%m.%Y')}–{date_to.strftime('%d.%m.%Y')}"


def absence_type_chip_class(absence_type: str) -> str:
    return _CHIP_CLASS_BY_TYPE.get(absence_type, "driver-absence-chip--other")


def _absence_search_text(absence: DriverAbsence, type_label: str, range_label: str, note: str) -> str:
    parts = [type_label, range_label, note, absence.absence_type]
    return " ".join(p for p in parts if p).casefold()


def build_driver_absence_display_rows(absences) -> list[dict]:
    rows: list[dict] = []
    for absence in absences:
        note = (absence.note or "").strip()
        type_label = absence.get_absence_type_display()
        range_label = format_absence_date_range(absence.date_from, absence.date_to)
        rows.append(
            {
                "type_label": type_label,
                "absence_type": absence.absence_type,
                "year": absence.date_from.year,
                "chip_class": absence_type_chip_class(absence.absence_type),
                "range_label": range_label,
                "is_partial": bool(absence.is_partial),
                "note": note,
                "note_preview": note[:48] + "…" if len(note) > 48 else note,
                "search_text": _absence_search_text(absence, type_label, range_label, note),
            }
        )
    return rows
