"""Sloučení více PDF pro hromadný tisk jedním dialogem."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

from django.conf import settings
from pypdf import PdfReader, PdfWriter

from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError, convert_xlsx_to_pdf, validate_print_media_rel

_PRINTABLE_KINDS = frozenset({"xlsx", "protocol", "zpo", "pio", "protocol_notes", "pdf"})
_XLSX_KINDS = frozenset({"xlsx"})
_EXCLUDED_FROM_ALL_KINDS = frozenset({"protocol", "protocol_notes", "pio"})
_EXCLUDED_FROM_ALL_WITH_PROTOCOL_KINDS = frozenset({"protocol_notes", "pio"})
_STREAM_PDF_MARKER = b"---PDF---\n"
BULK_MERGED_CACHE_SUBDIR = "bulk_merged"


def _merged_download_url(name: str) -> str:
    """URL pro stažení sloučeného PDF (autentizovaný view funguje i při DEBUG=False)."""
    try:
        from django.urls import reverse

        return reverse("waste_docs:bulk_merged_print_download", args=[name])
    except Exception:
        return f"/media/print_cache/{BULK_MERGED_CACHE_SUBDIR}/{name}"


def filter_file_rows_for_print_kind(file_rows: list[dict], print_kind: str) -> list[dict]:
    kind = (print_kind or "all").strip().lower()
    with_url = [row for row in file_rows if (row.get("print_url") or row.get("url")) and not row.get("warning")]
    if kind == "all_with_protocol":
        return [
            row
            for row in with_url
            if _is_printable_row(row)
            and (row.get("kind") or "").lower() not in _EXCLUDED_FROM_ALL_WITH_PROTOCOL_KINDS
        ]
    if not kind or kind == "all":
        return [
            row
            for row in with_url
            if _is_printable_row(row) and (row.get("kind") or "").lower() not in _EXCLUDED_FROM_ALL_KINDS
        ]
    return [row for row in with_url if (row.get("kind") or "").lower() == kind and _is_printable_row(row)]


def _is_printable_row(row: dict) -> bool:
    row_kind = (row.get("kind") or "").lower()
    if row_kind not in _PRINTABLE_KINDS:
        url = (row.get("print_url") or row.get("url") or "").lower()
        return url.endswith(".pdf")
    if row_kind in _XLSX_KINDS:
        return bool(row.get("print_url"))
    return True


def _media_rel_from_row_path(raw_path: str) -> str:
    path = Path(raw_path).resolve()
    return path.relative_to(settings.MEDIA_ROOT.resolve()).as_posix()


def _pdf_path_for_file_row(row: dict) -> Path:
    row_kind = (row.get("kind") or "").lower()
    media_rel = (row.get("media_rel") or "").strip()
    raw_path = (row.get("path") or "").strip()

    if row_kind in _XLSX_KINDS:
        if not media_rel and raw_path:
            try:
                media_rel = _media_rel_from_row_path(raw_path)
            except ValueError:
                media_rel = ""
        if not media_rel:
            raise XlsxToPdfError(f"Chybí cesta k souboru: {row.get('label') or row_kind}")
        source = validate_print_media_rel(media_rel)
        return convert_xlsx_to_pdf(source, media_rel=media_rel.replace("\\", "/").lstrip("/"))

    raw_path = (row.get("path") or "").strip()
    if raw_path:
        path = Path(raw_path)
        if path.is_file() and path.suffix.lower() == ".pdf":
            return path

    url = (row.get("url") or "").strip()
    if "/media/" in url:
        rel = url.split("/media/", 1)[1].split("?", 1)[0]
        path = settings.MEDIA_ROOT / rel.replace("/", "\\") if "\\" in str(settings.MEDIA_ROOT) else settings.MEDIA_ROOT / rel
        path = Path(str(path)).resolve()
        if path.is_file():
            return path

    raise XlsxToPdfError(f"PDF pro tisk není k dispozici: {row.get('label') or row_kind}")


def _merge_filtered_rows_to_bytes(filtered: list[dict]) -> bytes:
    writer = PdfWriter()
    for row in filtered:
        pdf_path = _pdf_path_for_file_row(row)
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    cache_dir = settings.MEDIA_ROOT / "print_cache" / BULK_MERGED_CACHE_SUBDIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    out_path = cache_dir / f"merged_{uuid.uuid4().hex}.pdf"
    with out_path.open("wb") as fh:
        writer.write(fh)
    try:
        return out_path.read_bytes()
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass


def build_merged_print_pdf_bytes(file_rows: list[dict], *, print_kind: str = "all") -> bytes:
    filtered = filter_file_rows_for_print_kind(file_rows, print_kind)
    if not filtered:
        raise XlsxToPdfError("Nebyly nalezeny soubory k tisku pro vybranou volbu.")
    return _merge_filtered_rows_to_bytes(filtered)


def stream_merged_print_pdf(file_rows: list[dict], *, print_kind: str = "all") -> Iterator[bytes]:
    """Postupné sloučení s řádky průběhu (JSON) a na konci marker + PDF bytes."""
    filtered = filter_file_rows_for_print_kind(file_rows, print_kind)
    if not filtered:
        raise XlsxToPdfError("Nebyly nalezeny soubory k tisku pro vybranou volbu.")

    writer = PdfWriter()
    total = len(filtered)
    for index, row in enumerate(filtered, start=1):
        label = (row.get("label") or row.get("kind") or "").strip()
        progress = {"type": "progress", "current": index, "total": total, "label": label}
        yield json.dumps(progress, ensure_ascii=False).encode("utf-8") + b"\n"
        pdf_path = _pdf_path_for_file_row(row)
        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            writer.add_page(page)

    buffer = BytesIO()
    writer.write(buffer)
    pdf_bytes = buffer.getvalue()

    cache_dir = settings.MEDIA_ROOT / "print_cache" / BULK_MERGED_CACHE_SUBDIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_name = f"merged_{uuid.uuid4().hex}.pdf"
    cached_path = cache_dir / cached_name
    cached_path.write_bytes(pdf_bytes)
    ready = {
        "type": "ready",
        "download_url": _merged_download_url(cached_name),
        "filename": cached_name,
    }
    yield json.dumps(ready, ensure_ascii=False).encode("utf-8") + b"\n"
    yield _STREAM_PDF_MARKER
    yield pdf_bytes
