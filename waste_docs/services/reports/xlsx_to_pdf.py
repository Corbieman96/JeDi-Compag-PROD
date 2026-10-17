"""Převod XLSX na PDF pro tisk v prohlížeči (Windows: MS Excel COM, fallback LibreOffice)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from django.conf import settings

_CONVERT_LOCK = threading.Lock()

ALLOWED_PRINT_REL_PREFIXES = ("pruvodky/", "protokoly/")

_LIBREOFFICE_CANDIDATES = (
    os.environ.get("LIBREOFFICE_SOFFICE_PATH", "").strip(),
    getattr(settings, "LIBREOFFICE_SOFFICE_PATH", "") or "",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


class XlsxToPdfError(RuntimeError):
    pass


def _cache_path_for_rel(media_rel: str) -> Path:
    safe_rel = media_rel.replace("\\", "/").lstrip("/")
    return settings.MEDIA_ROOT / "print_cache" / f"{safe_rel}.pdf"


def validate_print_media_rel(media_rel: str) -> Path:
    rel = (media_rel or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        raise XlsxToPdfError("Neplatná cesta souboru.")
    if not rel.lower().endswith(".xlsx"):
        raise XlsxToPdfError("Tisk podporuje jen soubory XLSX.")
    if not any(rel.startswith(prefix) for prefix in ALLOWED_PRINT_REL_PREFIXES):
        raise XlsxToPdfError("Soubor není v povoleném adresáři.")
    source = (settings.MEDIA_ROOT / rel).resolve()
    media_root = settings.MEDIA_ROOT.resolve()
    if media_root not in source.parents and source != media_root:
        raise XlsxToPdfError("Soubor mimo media.")
    if not source.is_file():
        raise XlsxToPdfError("Soubor neexistuje.")
    return source


def _project_tool_soffice_paths() -> list[Path]:
    base = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    tools = base / "tools"
    if not tools.is_dir():
        return []
    return sorted(p for p in tools.rglob("soffice.exe") if p.is_file())


def _find_soffice() -> Path | None:
    for candidate in _LIBREOFFICE_CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return path
    for path in _project_tool_soffice_paths():
        return path
    which = shutil.which("soffice")
    if which:
        return Path(which)
    return None


def _convert_with_excel_com(source: Path, dest: Path) -> None:
    if sys.platform != "win32":
        raise XlsxToPdfError("Převod přes MS Excel je dostupný jen na Windows serveru.")
    try:
        import win32com.client  # type: ignore[import-untyped]
        import pywintypes  # type: ignore[import-untyped]
    except ImportError as exc:
        raise XlsxToPdfError("Chybí balíček pywin32 pro převod Excel→PDF.") from exc

    dest.parent.mkdir(parents=True, exist_ok=True)
    excel = None
    workbook = None
    prog_ids = ("Excel.Application", "Excel.Application.16", "Excel.Application.15")
    last_com_error: Exception | None = None
    for prog_id in prog_ids:
        try:
            excel = win32com.client.DispatchEx(prog_id)
            break
        except pywintypes.com_error as exc:
            last_com_error = exc
            excel = None
    if excel is None:
        raise XlsxToPdfError(
            "MS Excel není na serveru nainstalovaný nebo není dostupný přes COM "
            "(zkontrolujte 64bit Office u 64bit Pythonu)."
        ) from last_com_error

    try:
        excel.Visible = False
        excel.DisplayAlerts = False
        workbook = excel.Workbooks.Open(str(source.resolve()))
        workbook.ExportAsFixedFormat(0, str(dest.resolve()))
    finally:
        if workbook is not None:
            workbook.Close(False)
        if excel is not None:
            excel.Quit()


def _convert_with_libreoffice(source: Path, dest: Path) -> None:
    soffice = _find_soffice()
    if soffice is None:
        raise XlsxToPdfError(
            "LibreOffice (soffice) není na serveru nainstalovaný. "
            "Nainstalujte LibreOffice nebo MS Excel na PC kde běží Django."
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    out_dir = dest.parent
    generated = out_dir / f"{source.stem}.pdf"
    if generated.exists():
        generated.unlink()

    cmd = [
        str(soffice),
        "--headless",
        "--norestore",
        "--nologo",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(source.resolve()),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise XlsxToPdfError("Převod XLSX→PDF přes LibreOffice trval příliš dlouho.") from exc
    except OSError as exc:
        raise XlsxToPdfError(f"Nelze spustit LibreOffice ({soffice}).") from exc

    if result.returncode != 0 or not generated.is_file():
        detail = (result.stderr or result.stdout or "").strip()
        raise XlsxToPdfError(
            "LibreOffice nepřevedl soubor na PDF."
            + (f" {detail}" if detail else "")
        )

    if generated.resolve() != dest.resolve():
        if dest.exists():
            dest.unlink()
        generated.replace(dest)


def _is_protocol_xlsx(source: Path) -> bool:
    from waste_docs.services.reports.protocol_page_setup import is_protocol_xlsx_path

    return is_protocol_xlsx_path(source)


def invalidate_print_cache_for_source(source: Path, *, media_rel: str | None = None) -> None:
    if media_rel is None:
        try:
            media_rel = source.resolve().relative_to(settings.MEDIA_ROOT.resolve()).as_posix()
        except ValueError:
            return
    cache_path = _cache_path_for_rel(media_rel.replace("\\", "/").lstrip("/"))
    cache_path.unlink(missing_ok=True)


def _convert_xlsx_to_pdf_file(source: Path, dest: Path) -> None:
    if _is_protocol_xlsx(source):
        from waste_docs.services.reports.protocol_page_setup import convert_protocol_xlsx_to_pdf

        with _CONVERT_LOCK:
            convert_protocol_xlsx_to_pdf(source, dest)
        return

    errors: list[str] = []
    with _CONVERT_LOCK:
        try:
            _convert_with_excel_com(source, dest)
            return
        except XlsxToPdfError as exc:
            errors.append(str(exc))
        try:
            _convert_with_libreoffice(source, dest)
            return
        except XlsxToPdfError as exc:
            errors.append(str(exc))
        try:
            from waste_docs.services.reports.xlsx_basic_pdf import (
                BasicXlsxPdfError,
                convert_xlsx_to_basic_pdf,
            )

            convert_xlsx_to_basic_pdf(source, dest)
            return
        except BasicXlsxPdfError as exc:
            errors.append(str(exc))

    raise XlsxToPdfError(
        "Převod XLSX→PDF selhal. Nainstalujte LibreOffice: python manage.py setup_print_converter "
        + " | ".join(errors)
    )


def convert_xlsx_to_pdf(source: Path, *, media_rel: str | None = None) -> Path:
    """Převede XLSX na PDF; použije cache pokud je aktuální."""
    if media_rel is None:
        try:
            media_rel = source.resolve().relative_to(settings.MEDIA_ROOT.resolve()).as_posix()
        except ValueError as exc:
            raise XlsxToPdfError("Soubor není v MEDIA_ROOT.") from exc
    cache_path = _cache_path_for_rel(media_rel)
    if cache_path.is_file() and cache_path.stat().st_mtime >= source.stat().st_mtime:
        return cache_path
    if _is_protocol_xlsx(source):
        invalidate_print_cache_for_source(source, media_rel=media_rel)
    _convert_xlsx_to_pdf_file(source, cache_path)
    return cache_path


def print_url_for_media_rel(media_rel: str) -> str:
    from urllib.parse import urlencode

    from django.urls import reverse

    rel = media_rel.replace("\\", "/").lstrip("/")
    return f"{reverse('waste_docs:print_file_as_pdf')}?{urlencode({'rel': rel})}"
