"""Dlouhé poznámky v protokolu jizda.xlsx — zkrácení v buňce a PDF doplněk."""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from waste_docs.activity_fields import activity_uses_fulfillment_address, protocol_address_snapshot_for_ride
from waste_docs.models import Pruvodka
from waste_docs.services.reports.reportlab_unicode_font import ensure_reportlab_unicode_font

# Buňka POZNAMKA v jizda.xlsx: sloučení C:K, Arial 10, výška řádku ~14 pt (jeden řádek).
# PDF doplněk musí mít Unicode TTF — Helvetica neumí českou diakritiku.
PROTOCOL_NOTE_FONT = ensure_reportlab_unicode_font()
PROTOCOL_NOTE_FONT_SIZE = 10.0
PROTOCOL_NOTE_MAX_WIDTH_PT = 480.0
SUPPLEMENT_SUFFIX = "… (viz list Poznámky)"


def _note_text_width(text: str) -> float:
    return stringWidth(text, PROTOCOL_NOTE_FONT, PROTOCOL_NOTE_FONT_SIZE)


def protocol_note_for_cell(note: str) -> tuple[str, bool]:
    """Vrátí text do buňky protokolu a zda je potřeba PDF doplněk."""
    text = (note or "").strip()
    if not text:
        return "", False
    if _note_text_width(text) <= PROTOCOL_NOTE_MAX_WIDTH_PT:
        return text, False
    suffix = SUPPLEMENT_SUFFIX
    budget = PROTOCOL_NOTE_MAX_WIDTH_PT - _note_text_width(suffix)
    if budget <= 0:
        return suffix.strip(), True
    trimmed = text
    while trimmed and _note_text_width(trimmed) > budget:
        trimmed = trimmed[:-1].rstrip()
    if not trimmed:
        return suffix.strip(), True
    return f"{trimmed}{suffix}", True


def rides_needing_note_supplement(rides: list[Pruvodka]) -> list[Pruvodka]:
    out: list[Pruvodka] = []
    for ride in rides:
        _, needs = protocol_note_for_cell(ride.contact_note or "")
        if needs:
            out.append(ride)
    return out


def _driver_label(ride: Pruvodka) -> str:
    snap = (ride.driver_snapshot or "").strip()
    if snap:
        return snap
    if ride.driver_id and ride.driver:
        parts = [ride.driver.first_name or "", ride.driver.last_name or ""]
        return " ".join(p for p in parts if p).strip() or "—"
    return "—"


def _wrap_lines(text: str, max_width: float, font_name: str, font_size: float) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_protocol_note_supplement_pdf_bytes(rides: list[Pruvodka]) -> bytes:
    """PDF — jedna stránka na jízdu s dlouhou poznámkou."""
    supplement_rides = rides_needing_note_supplement(rides)
    if not supplement_rides:
        return b""

    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 18 * mm
    content_w = page_w - 2 * margin
    c = canvas.Canvas(buf, pagesize=A4)

    header_h = 14 * mm
    green = (0.05, 0.32, 0.12)

    for ride in supplement_rides:
        note = (ride.contact_note or "").strip()
        drive_date = ride.drive_date.strftime("%d.%m.%Y") if ride.drive_date else "—"
        snd = (ride.snd_cislo_listu or "").strip() or "—"
        rz = (ride.vehicle_rz_snapshot or "").strip() or "—"

        c.setFillColorRGB(*green)
        c.rect(0, page_h - header_h, page_w, header_h, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(PROTOCOL_NOTE_FONT, 14)
        c.drawString(margin, page_h - header_h + 4 * mm, "Poznámka k jízdě")

        y = page_h - header_h - 8 * mm
        c.setFillColorRGB(0, 0, 0)
        c.setFont(PROTOCOL_NOTE_FONT, 11)
        meta_lines = [
            f"Jízda #{ride.pk}  ·  SND {snd}  ·  {drive_date}",
            f"RZ: {rz}  ·  Řidič: {_driver_label(ride)}",
            f"Subjekt: {(ride.name_snapshot or '').strip() or '—'}",
        ]
        if activity_uses_fulfillment_address(ride.activity_id):
            addr = protocol_address_snapshot_for_ride(ride.address_snapshot, ride.activity_id)
            meta_lines.append(f"Adresa: {addr or '—'}")
        meta_lines.append(f"Odpad: {(ride.waste_type_snapshot or '').strip() or '—'}")
        meta_lines.append(f"Koncovka: {(ride.suffix_snapshot or '').strip() or '—'}")
        for line in meta_lines:
            for wrapped in _wrap_lines(line, content_w, PROTOCOL_NOTE_FONT, 11):
                c.drawString(margin, y, wrapped)
                y -= 5 * mm

        y -= 3 * mm
        c.setFont(PROTOCOL_NOTE_FONT, 11)
        c.drawString(margin, y, "Poznámka:")
        y -= 6 * mm
        c.setFont(PROTOCOL_NOTE_FONT, 10)
        for line in _wrap_lines(note, content_w, PROTOCOL_NOTE_FONT, 10):
            if y < margin:
                break
            c.drawString(margin, y, line)
            y -= 4.5 * mm

        c.showPage()

    c.save()
    return buf.getvalue()


def protocol_note_supplement_filename_token(
    rides: list[Pruvodka],
    *,
    scope: str | None = None,
    selected_date=None,
) -> str:
    from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_DAY, protocol_filename_token

    return protocol_filename_token(
        rides,
        scope=scope or PROTOCOL_SCOPE_DAY,
        selected_date=selected_date,
    )
