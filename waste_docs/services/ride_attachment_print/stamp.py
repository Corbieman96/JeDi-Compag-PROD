"""Razítko čísla listu a data jízdy do PDF přílohy."""

from __future__ import annotations

import io
import logging
from datetime import date

logger = logging.getLogger(__name__)


def stamp_label_lines(*, snd_cislo_listu: str, drive_date: date | None, ride_pk: int) -> list[str]:
    """Textové řádky razítka: číslo jízdy + datum."""
    snd = (snd_cislo_listu or "").strip() or f"Jízda #{ride_pk}"
    lines = [snd]
    if drive_date:
        lines.append(drive_date.strftime("%d.%m.%Y"))
    return lines


def _layout(width: float, height: float, lines: list[str], text_width) -> tuple[float, list[tuple[str, float]], float]:
    """Vrátí (x, [(line, y), ...], fontsize) — pravý dolní roh."""
    margin = max(12.0, min(width, height) * 0.03)
    fs = max(9.0, min(14.0, width * 0.028))
    line_gap = fs * 1.25
    max_w = max((text_width(line, fs) for line in lines), default=0.0)
    x = max(margin, width - margin - max_w)
    # y od spodní hrany stránky (reportlab / mediabox)
    base_y = margin + fs * 0.2
    positioned: list[tuple[str, float]] = []
    for i, line in enumerate(reversed(lines)):
        positioned.append((line, base_y + i * line_gap))
    positioned.reverse()
    return x, positioned, fs


def _stamp_fitz(pdf_bytes: bytes, lines: list[str]) -> bytes:
    import fitz

    if not lines:
        return pdf_bytes
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if doc.page_count < 1:
            return pdf_bytes
        if doc.is_encrypted:
            try:
                doc.authenticate("")
            except (RuntimeError, ValueError, TypeError):
                pass
            if doc.needs_pass:
                logger.warning("Příloha PDF je zašifrovaná — razítko nelze doplnit.")
                return pdf_bytes

        def text_width(s: str, fs: float) -> float:
            return float(fitz.get_text_length(s, fontname="helv", fontsize=fs))

        for page in doc:
            r = page.rect
            width, height = float(r.width), float(r.height)
            x, positioned, fs = _layout(width, height, lines, text_width)
            for line, y_from_bottom in positioned:
                y = r.y1 - y_from_bottom
                page.insert_text(
                    (x, y),
                    line,
                    fontsize=fs,
                    fontname="helv",
                    color=(0.05, 0.32, 0.12),
                )
        return doc.tobytes()
    finally:
        doc.close()


def _stamp_overlay(pdf_bytes: bytes, lines: list[str]) -> bytes:
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    if not lines:
        return pdf_bytes
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        return pdf_bytes

    writer = PdfWriter()
    writer.append(reader)

    for page_index, base_page in enumerate(writer.pages):
        mb = base_page.mediabox
        width = float(mb.width)
        height = float(mb.height)
        overlay_bio = io.BytesIO()
        c = canvas.Canvas(overlay_bio, pagesize=(width, height))
        c.setFillColorRGB(0.05, 0.32, 0.12)

        def text_width(s: str, fs: float) -> float:
            return c.stringWidth(s, "Helvetica", fs)

        x, positioned, fs = _layout(width, height, lines, text_width)
        c.setFont("Helvetica", fs)
        for line, y in positioned:
            c.drawString(x, y, line)
        c.showPage()
        c.save()
        overlay_bio.seek(0)
        overlay_page = PdfReader(overlay_bio).pages[0]
        writer.pages[page_index].merge_page(overlay_page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def stamp_attachment_pdf_bytes(
    pdf_bytes: bytes,
    *,
    snd_cislo_listu: str,
    drive_date: date | None,
    ride_pk: int,
) -> bytes:
    """Do PDF vloží číslo listu a datum jízdy (všechny stránky, pravý dolní roh)."""
    lines = stamp_label_lines(
        snd_cislo_listu=snd_cislo_listu,
        drive_date=drive_date,
        ride_pk=ride_pk,
    )
    try:
        return _stamp_fitz(pdf_bytes, lines)
    except ImportError as exc:
        logger.debug("PyMuPDF nedostupné (%s), použije se reportlab overlay.", exc)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.debug("Razítko PyMuPDF selhalo (%s), použije se reportlab overlay.", exc)
    return _stamp_overlay(pdf_bytes, lines)
