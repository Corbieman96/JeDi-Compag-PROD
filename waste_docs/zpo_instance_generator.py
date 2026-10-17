"""
Z vzorového ZPO (číselník) vytvoří nový soubor s číslem listu/jízdy a uloží ho k průvodce.

PDF: 1) pokus o vyplnění AcroForm polí (klíčová slova v názvu pole nebo jediné textové pole);
     2) razítko čísla vpravo dole — PyMuPDF (fitz), při nedostupnosti fallback reportlab overlay + pypdf merge.
Obrázky (PNG/JPG): vytiskne číslo vpravo dole.
Excel (.xlsx): nahradí placeholdery {{SND_CISLO_LISTU_}} atd.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from django.core.files.storage import default_storage
from pypdf.errors import PyPdfError

from waste_docs.zpo_resolved import effective_zpo_file, pair_for_pruvodka, zpo_kind_for_file
from waste_docs.services.zpo_instance_cleanup import (
    cleanup_zpo_instance_orphans_for_pruvodka,
    save_zpo_instance_bytes,
)
from waste_docs.services.zpo_instance_staleness import zpo_instance_needs_regeneration
from waste_docs.services.zpo_instance_status import (
    clear_zpo_ensure_failure,
    record_zpo_ensure_failure,
)
from waste_docs.services.zpo_xlsx_stamp import build_zpo_xlsx_bytes

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka

logger = logging.getLogger(__name__)

# Zvyšte po změně algoritmu (razítko / formulář), aby se u existujících průvodky přegenerovalo ZPO.
CURRENT_ZPO_GENERATOR_REVISION = 8

# Velikost a pozice razítka — odpovídá číslovaným položkám typu „2)“ v šabloně ZPO.
ZPO_SND_FONT_PT = 10.0
ZPO_SND_MARGIN_RIGHT_PT = 40.0
ZPO_SND_MARGIN_BOTTOM_PT = 22.0

_SND_FIELD_KEYWORDS = (
    "cislo_listu",
    "snd_cislo",
    "ciselnik",
    "listu_jizdy",
    "cislo_listu_jizdy",
    "cislo_pas",
    "snd_list",
    "cislo",  # často v českých šablonách: „číslo“, normalizace níže
    "listu",
    "list",
    "jizdy",
    "jízdy",
    "pasu",
    "evidence",
)


def _pair_for_item(item: Pruvodka):
    if not (item.name_id and item.waste_type_id and item.suffix_id):
        return None
    return pair_for_pruvodka(item)


def _normalize_field_name(name: str) -> str:
    s = (name or "").lower().replace(" ", "_")
    for ch, repl in (("á", "a"), ("č", "c"), ("ď", "d"), ("é", "e"), ("ě", "e"), ("í", "i"), ("ň", "n"), ("ó", "o"), ("ř", "r"), ("š", "s"), ("ť", "t"), ("ú", "u"), ("ů", "u"), ("ý", "y"), ("ž", "z")):
        s = s.replace(ch, repl)
    return s


def _collect_pdf_field_updates(reader, snd: str) -> dict[str, str]:
    try:
        fields = reader.get_form_text_fields() or {}
    except (PyPdfError, AttributeError, TypeError) as exc:
        logger.debug("Nelze načíst AcroForm pole PDF: %s", exc)
        return {}
    if not fields:
        return {}
    out: dict[str, str] = {}
    for name in fields:
        low = _normalize_field_name(name)
        if any(k in low for k in _SND_FIELD_KEYWORDS):
            out[name] = snd
    if not out and len(fields) == 1:
        out[next(iter(fields))] = snd
    return out


def _zpo_stamp_layout(width: float, height: float, snd: str, text_width_fn) -> tuple[float, float, float]:
    """Vrátí (x, y, font_size) pro vodorovné razítko vpravo dole. y je od spodní hrany stránky (ReportLab)."""
    fs = ZPO_SND_FONT_PT
    tw = text_width_fn(snd, fs)
    x = max(ZPO_SND_MARGIN_RIGHT_PT, width - ZPO_SND_MARGIN_RIGHT_PT - tw)
    y = ZPO_SND_MARGIN_BOTTOM_PT
    return x, y, fs


def _stamp_snd_fitz(pdf_bytes: bytes, snd: str) -> bytes:
    """Do PDF vloží viditelné číslo listu/jízdy (pravý dolní roh poslední stránky)."""
    import fitz

    snd = (snd or "").strip()
    if not snd:
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
                logger.warning("ZPO PDF je zašifrované — číslo listu do souboru nelze doplnit.")
                return pdf_bytes

        page = doc[-1]
        r = page.rect
        width, height = float(r.width), float(r.height)

        def text_width(s: str, fs: float) -> float:
            return float(fitz.get_text_length(s, fontname="helv", fontsize=fs))

        x, y_bottom, fs = _zpo_stamp_layout(width, height, snd, text_width)
        y = r.y1 - y_bottom
        page.insert_text(
            (x, y),
            snd,
            fontsize=fs,
            fontname="helv",
            color=(0.05, 0.32, 0.12),
        )
        return doc.tobytes()
    finally:
        doc.close()


def _stamp_snd_overlay(pdf_bytes: bytes, snd: str) -> bytes:
    """Do PDF vloží viditelný text v content streamu (fallback bez PyMuPDF)."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas

    snd = (snd or "").strip()
    if not snd:
        return pdf_bytes
    reader = PdfReader(io.BytesIO(pdf_bytes))
    if not reader.pages:
        return pdf_bytes

    base_page = reader.pages[-1]
    mb = base_page.mediabox
    width = float(mb.width)
    height = float(mb.height)

    overlay_bio = io.BytesIO()
    c = canvas.Canvas(overlay_bio, pagesize=(width, height))
    c.setFillColorRGB(0.05, 0.32, 0.12)

    def text_width(s: str, fs: float) -> float:
        return c.stringWidth(s, "Helvetica", fs)

    x, y, fs = _zpo_stamp_layout(width, height, snd, text_width)
    c.setFont("Helvetica", fs)
    c.drawString(x, y, snd)
    c.showPage()
    c.save()
    overlay_bio.seek(0)

    overlay_page = PdfReader(overlay_bio).pages[0]
    writer = PdfWriter()
    writer.append(reader)
    writer.pages[-1].merge_page(overlay_page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _stamp_snd(pdf_bytes: bytes, snd: str) -> bytes:
    """Razítko čísla listu — preferuje PyMuPDF, při chybě fallback reportlab overlay."""
    if not (snd or "").strip():
        return pdf_bytes
    try:
        return _stamp_snd_fitz(pdf_bytes, snd)
    except ImportError as exc:
        logger.debug("PyMuPDF nedostupné (%s), použije se reportlab overlay.", exc)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        logger.debug("Razítko PyMuPDF selhalo (%s), použije se reportlab overlay.", exc)
    return _stamp_snd_overlay(pdf_bytes, snd)


def _build_pdf_bytes_from_bytes(data: bytes, item: Pruvodka) -> bytes:
    """Vždy doplní číslo listu do výstupního PDF (razítko); volitelně předtím AcroForm."""
    from pypdf import PdfReader, PdfWriter

    snd = (item.snd_cislo_listu or "").strip()
    reader = PdfReader(io.BytesIO(data))
    updates = _collect_pdf_field_updates(reader, snd)
    if updates:
        try:
            writer = PdfWriter()
            writer.append(reader)
            for page in writer.pages:
                try:
                    writer.update_page_form_field_values(page, updates, auto_regenerate=True)
                    break
                except PyPdfError:
                    continue
            bio = io.BytesIO()
            writer.write(bio)
            data = bio.getvalue()
        except PyPdfError as exc:
            logger.warning("Vyplnění PDF formuláře (pypdf) selhalo, použije se jen razítko: %s", exc)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Vyplnění PDF formuláře selhalo (I/O nebo data), použije se jen razítko: %s", exc)

    if snd:
        data = _stamp_snd(data, snd)
    return data


def _build_pdf_bytes(template_file, item: Pruvodka) -> bytes:
    with template_file.open("rb") as f:
        data = f.read()
    return _build_pdf_bytes_from_bytes(data, item)


def _build_image_bytes(template_file, item: Pruvodka, ext: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    with template_file.open("rb") as f:
        raw = f.read()
    img = Image.open(io.BytesIO(raw))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    draw = ImageDraw.Draw(img)
    text = item.snd_cislo_listu or ""
    w, h = img.size
    font_size = max(14, min(36, int(h * 0.04)))
    font = None
    for font_name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "calibri.ttf"):
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(8, int(min(w, h) * 0.015))
    draw.text((w - tw - pad, h - th - pad), text, fill=(25, 100, 45, 255), font=font)
    out = io.BytesIO()
    if ext.lower() in (".jpg", ".jpeg"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "RGBA":
            bg.paste(img, mask=img.split()[3])
        else:
            bg.paste(img)
        bg.save(out, format="JPEG", quality=92)
    else:
        img.save(out, format="PNG")
    return out.getvalue()


def _copy_template_bytes(template_file) -> bytes:
    with template_file.open("rb") as f:
        return f.read()


def ensure_zpo_instance_for_pruvodka_pk(pk: int, *, force: bool = False) -> bool:
    from waste_docs.models import Pruvodka

    try:
        item = Pruvodka.objects.get(pk=pk)
    except Pruvodka.DoesNotExist:
        return False
    return ensure_zpo_instance_for_pruvodka(item, force=force)


def ensure_zpo_instance_for_pruvodka(item: Pruvodka, *, force: bool = False) -> bool:
    """Idempotentně vytvoří / obnoví zpo_instance_file podle aktuálního čísla listu."""
    from waste_docs.models import Pruvodka
    from waste_docs.zpo_policy import explain_system_zpo_generation_block

    snd = (item.snd_cislo_listu or "").strip()
    if not snd:
        return True

    block = explain_system_zpo_generation_block(item)
    if block:
        record_zpo_ensure_failure(item.pk, block)
        return False

    pair = _pair_for_item(item)
    template = effective_zpo_file(pair)
    if not template:
        if not (item.name_id and item.waste_type_id and item.suffix_id):
            record_zpo_ensure_failure(item.pk, "chybí subjekt, druh odpadu nebo koncovku")
        elif pair is None:
            record_zpo_ensure_failure(item.pk, "v číselníku není pár subjekt + odpad + koncovka")
        else:
            record_zpo_ensure_failure(item.pk, "k páru není přiřazen vzor ZPO v knihovně")
        return False

    template_name = (getattr(template, "name", None) or "").strip()
    if template_name and not default_storage.exists(template_name):
        record_zpo_ensure_failure(item.pk, "soubor vzoru ZPO na disku chybí")
        return False

    if not zpo_instance_needs_regeneration(item, pair=pair, force=force):
        clear_zpo_ensure_failure(item.pk)
        return True

    has_file = bool(item.zpo_instance_file and item.zpo_instance_file.name)
    old_stored_name = item.zpo_instance_file.name if has_file and item.zpo_instance_file.name else ""

    ext = Path(template.name).suffix.lower() or ".pdf"
    safe_snd = item.snd_cislo_listu.replace("/", "-").replace("\\", "-")
    rel = f"pruvodky/zpo_instance/{item.pk}_{safe_snd}{ext}"

    try:
        kind = zpo_kind_for_file(template)
        if kind == "pdf":
            payload = _build_pdf_bytes(template, item)
        elif kind == "xlsx":
            payload = build_zpo_xlsx_bytes(template, item)
        elif kind == "image":
            payload = _build_image_bytes(template, item, ext)
        else:
            raw = _copy_template_bytes(template)
            # Soubor bez přípony .pdf ale ve skutečnosti PDF
            if len(raw) >= 5 and raw[:5] == b"%PDF-":
                payload = _build_pdf_bytes_from_bytes(raw, item)
            else:
                payload = raw
        stored_name = save_zpo_instance_bytes(rel, payload)
    except PyPdfError as exc:
        logger.exception("Generování ZPO (PDF) pro průvodku %s selhalo: %s", item.pk, exc)
        record_zpo_ensure_failure(item.pk, f"chyba PDF: {exc}")
        return False
    except OSError as exc:
        logger.exception("Generování ZPO (soubor/úložiště) pro průvodku %s selhalo: %s", item.pk, exc)
        record_zpo_ensure_failure(item.pk, f"chyba souboru: {exc}")
        return False
    except (ValueError, TypeError) as exc:
        logger.exception("Generování ZPO (neplatná data) pro průvodku %s selhalo: %s", item.pk, exc)
        record_zpo_ensure_failure(item.pk, f"neplatná data: {exc}")
        return False
    except Exception as exc:
        logger.exception("Generování ZPO pro průvodku %s selhalo (nečekaná chyba): %s", item.pk, exc)
        record_zpo_ensure_failure(item.pk, str(exc))
        return False

    Pruvodka.objects.filter(pk=item.pk).update(
        zpo_instance_file=stored_name,
        zpo_instance_for_snd=item.snd_cislo_listu,
        zpo_generator_revision=CURRENT_ZPO_GENERATOR_REVISION,
    )
    from waste_docs.services.manual_print_marks import clear_pruvodka_print_marks

    refreshed = Pruvodka.objects.filter(pk=item.pk).first()
    if refreshed:
        clear_pruvodka_print_marks(
            refreshed,
            old_zpo_stored_name=old_stored_name if old_stored_name != stored_name else "",
        )
    if old_stored_name and old_stored_name != stored_name:
        try:
            default_storage.delete(old_stored_name)
        except OSError as exc:
            logger.warning("Smazání starého ZPO po přegenerování selhalo: %s", exc)
    cleanup_zpo_instance_orphans_for_pruvodka(item.pk, keep_name=stored_name)
    clear_zpo_ensure_failure(item.pk)
    return True
