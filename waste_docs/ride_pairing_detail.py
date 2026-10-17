"""Textový „detail jízdy“ pro párování s dokumentem ZPO (pas / dávka)."""

from __future__ import annotations

from datetime import date

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)

from waste_docs.models import Pruvodka


def _cell(value) -> str:
    if value is None:
        return "—"
    s = str(value).strip()
    return s if s else "—"


def build_ride_detail_lines_draft(
    *,
    name_id: int | None,
    waste_type_id: int | None,
    suffix_id: int | None,
    activity_id: int | None = None,
    vehicle_rz_id: int | None = None,
    driver_id: int | None = None,
    drive_date: date | None = None,
    container_number: str = "",
    contact_phone: str = "",
    contact_note: str = "",
    fulfillment_address_value: str = "",
    facility_address_display: str = "",
) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    if drive_date:
        lines.append({"label": "Datum jízdy", "value": drive_date.strftime("%d.%m.%Y")})
    else:
        lines.append({"label": "Datum jízdy", "value": "—"})

    if activity_id:
        act = ActivityCatalog.objects.filter(pk=activity_id).first()
        lines.append({"label": "Činnost", "value": _cell(act.name if act else None)})
    else:
        lines.append({"label": "Činnost", "value": "—"})

    if vehicle_rz_id:
        rz = VehicleRzCatalog.objects.filter(pk=vehicle_rz_id).first()
        lines.append({"label": "RZ vozidla", "value": _cell(rz.value if rz else None)})
    else:
        lines.append({"label": "RZ vozidla", "value": "—"})

    if driver_id:
        d = DriverProfile.objects.filter(pk=driver_id).first()
        if d:
            full = " ".join(p for p in [d.title, d.first_name, d.last_name] if p).strip()
            lines.append({"label": "Řidič", "value": _cell(full or d.personal_number)})
        else:
            lines.append({"label": "Řidič", "value": "—"})
    else:
        lines.append({"label": "Řidič", "value": "—"})

    if name_id:
        nm = NameCatalog.objects.filter(pk=name_id).first()
        lines.append({"label": "Název F/P", "value": _cell(nm.value if nm else None)})
    else:
        lines.append({"label": "Název F/P", "value": "—"})

    if waste_type_id:
        wt = WasteTypeCatalog.objects.filter(pk=waste_type_id).first()
        lines.append({"label": "Druh odpadu", "value": _cell(wt.value if wt else None)})
    else:
        lines.append({"label": "Druh odpadu", "value": "—"})

    if suffix_id:
        sf = SuffixCatalog.objects.filter(pk=suffix_id).first()
        lines.append({"label": "Koncovka", "value": _cell(sf.value if sf else None)})
    else:
        lines.append({"label": "Koncovka", "value": "—"})

    lines.append({"label": "Adresa plnění", "value": _cell(fulfillment_address_value)})
    lines.append({"label": "Provoz", "value": _cell(facility_address_display)})
    lines.append({"label": "Kontejner (1)", "value": _cell(container_number)})
    lines.append({"label": "Telefon", "value": _cell(contact_phone)})
    lines.append({"label": "Poznámka", "value": _cell(contact_note)})
    return lines


def build_ride_detail_lines_from_pruvodka(item: Pruvodka) -> list[dict[str, str]]:
    return [
        {"label": "Číslo listu/jízdy", "value": _cell(item.snd_cislo_listu)},
        {"label": "Datum jízdy", "value": item.drive_date.strftime("%d.%m.%Y")},
        {"label": "Činnost", "value": _cell(item.activity_snapshot)},
        {"label": "RZ vozidla", "value": _cell(item.vehicle_rz_snapshot)},
        {"label": "Řidič", "value": _cell(item.driver_snapshot)},
        {"label": "Název F/P", "value": _cell(item.name_snapshot)},
        {"label": "IČO", "value": _cell(item.ico_snapshot)},
        {"label": "Adresa", "value": _cell(item.address_snapshot)},
        {"label": "Druh odpadu", "value": _cell(item.waste_type_snapshot)},
        {"label": "Kat. číslo", "value": _cell(item.waste_code_snapshot)},
        {"label": "Kategorie", "value": _cell(item.waste_category_snapshot)},
        {"label": "Koncovka", "value": _cell(item.suffix_snapshot)},
        {"label": "Kontejner (1)", "value": _cell(item.container_number)},
        {"label": "Kontejner (2)", "value": _cell(item.container_number_2)},
        {"label": "Telefon", "value": _cell(item.contact_phone)},
        {"label": "Poznámka", "value": _cell(item.contact_note)},
    ]
