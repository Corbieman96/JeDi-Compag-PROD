"""Post-save úprava pageSetup v XLSX protokolu — landscape A1:M38 bez printerSettings."""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from waste_docs.services.reports.protocol_print_settings import (
    _strip_page_setup_printer_attrs,
    validate_generated_xlsx,
)

PROTOCOL_PAGE_SETUP_TAG = (
    '<pageSetup orientation="landscape" paperSize="9" fitToHeight="0"/>'
)
PROTOCOL_FIT_TO_PAGE_TAG = '<pageSetUpPr fitToPage="1" />'


def _ensure_fit_to_page(sheet_xml: str) -> str:
    if "fitToPage=" in sheet_xml:
        return sheet_xml
    if "<sheetPr>" in sheet_xml:
        return sheet_xml.replace(
            "<sheetPr>",
            f"<sheetPr>{PROTOCOL_FIT_TO_PAGE_TAG}",
            1,
        )
    if "<sheetPr " in sheet_xml:
        return re.sub(
            r"(<sheetPr\b[^>]*>)",
            rf"\1{PROTOCOL_FIT_TO_PAGE_TAG}",
            sheet_xml,
            count=1,
        )
    return sheet_xml


def _patch_protocol_sheet_page_setup(sheet_xml: str) -> str:
    text = _strip_page_setup_printer_attrs(sheet_xml)
    text = _ensure_fit_to_page(text)
    if re.search(r"<pageSetup\b", text):
        patched, count = re.subn(
            r"<pageSetup\b[^>]*/>",
            PROTOCOL_PAGE_SETUP_TAG,
            text,
            count=1,
        )
        if count:
            return patched
        patched, count = re.subn(
            r"<pageSetup\b[^>]*>.*?</pageSetup>",
            PROTOCOL_PAGE_SETUP_TAG,
            text,
            count=1,
            flags=re.DOTALL,
        )
        if count:
            return patched
    return text.replace(
        "</worksheet>",
        f"{PROTOCOL_PAGE_SETUP_TAG}</worksheet>",
        1,
    )


def ensure_protocol_page_setup_in_xlsx(xlsx_path: Path) -> bool:
    """Vynutí landscape pageSetup na všech listech; bez printerSettings vztahu."""
    path = Path(xlsx_path)
    if not path.is_file():
        return False

    with zipfile.ZipFile(path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    changed = False
    sheet_paths = sorted(
        name for name in entries if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )
    for sheet_path in sheet_paths:
        sheet_xml = entries[sheet_path].decode("utf-8")
        patched = _patch_protocol_sheet_page_setup(sheet_xml)
        if patched != sheet_xml:
            changed = True
            entries[sheet_path] = patched.encode("utf-8")

    if not changed:
        return False

    fd, temp_name = tempfile.mkstemp(suffix=path.suffix)
    try:
        import os

        os.close(fd)
        temp_path = Path(temp_name)
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, data in entries.items():
                target.writestr(name, data)
        shutil.move(str(temp_path), str(path))
        validate_generated_xlsx(path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return True
