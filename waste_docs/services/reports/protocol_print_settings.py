"""Nastavení tiskárny v protokolu — jednostranný tisk (A1:M38).

Openpyxl při ukládání zahazuje pageSetup → printerSettings. Po save generátor:
1) odstraní duplex blob z výstupu,
2) vynutí landscape pageSetup (A1:M38),
3) zkopíruje jednostranný printerSettings blob jen ze šablony jizda.xlsx (bez fallback .bin).
"""

from __future__ import annotations

import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PRINTER_SETTINGS_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/printerSettings"
)
PRINTER_SETTINGS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.printerSettings"
)
PRINTER_SETTINGS_PART = "xl/printerSettings/printerSettings1.bin"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


VBA_PROJECT_PART = "xl/vbaProject.bin"
VBA_PROJECT_CONTENT_TYPE = "application/vnd.ms-office.vbaProject"
PROTOCOL_PRINT_MACRO_NAME = "TiskCelySesit"
_VBA_ARCHIVE_PREFIXES = ("xl/vba", "xl/ctrlProps", "customUI", "xl/activeX")


def resolve_protocol_template_path(template_path: Path | None = None) -> Path:
    """jizda.xlsx — hlavní šablona (tisk nastavte v Excelu). jizda.xlsm jen pokud xlsx chybí."""
    if template_path is not None:
        return Path(template_path)
    from django.conf import settings

    base = Path(settings.BASE_DIR)
    xlsm = base / "jizda.xlsm"
    xlsx = base / "jizda.xlsx"
    if xlsx.is_file():
        return xlsx
    if xlsm.is_file():
        return xlsm
    return xlsx


def should_keep_vba_for_template(template_path: Path) -> bool:
    return template_has_vba_project(template_path)


def validate_generated_xlsx(xlsx_path: Path) -> None:
    """Ověří, že výstupní soubor není poškozený ZIP/XLSX."""
    with zipfile.ZipFile(xlsx_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"Vygenerovaný protokol je poškozený (soubor v archivu: {bad}).")


def template_has_vba_project(template_path: Path) -> bool:
    if not template_path.is_file():
        return False
    with zipfile.ZipFile(template_path) as archive:
        return VBA_PROJECT_PART in archive.namelist()


def template_has_printer_settings(template_path: Path) -> bool:
    if not template_path.is_file():
        return False
    with zipfile.ZipFile(template_path) as archive:
        return any(
            name.startswith("xl/printerSettings/") and name.endswith(".bin")
            for name in archive.namelist()
        )


def read_template_printer_settings(template_path: Path) -> bytes | None:
    if not template_path.is_file():
        return None
    with zipfile.ZipFile(template_path) as archive:
        for name in sorted(archive.namelist()):
            if name.startswith("xl/printerSettings/") and name.endswith(".bin"):
                return archive.read(name)
    return None


def _strip_page_setup_printer_attrs(sheet_xml: str) -> str:
    """Odstraní printerSettings atributy jen z tagu pageSetup (ne z drawing apod.)."""

    def _repl(match: re.Match[str]) -> str:
        attrs = match.group(2)
        attrs = re.sub(r'\s*r:id="[^"]*"', "", attrs)
        attrs = re.sub(r'\s*usePrinterDefaults="[^"]*"', "", attrs)
        return f"{match.group(1)}{attrs}{match.group(3)}"

    return re.sub(r"(<pageSetup\b)([^>]*)(/?>)", _repl, sheet_xml, count=1)


def _repair_sheet_drawing_rids(entries: dict[str, bytes]) -> bool:
    """Doplní chybějící r:id u drawing tagu podle vztahu v sheet .rels."""
    changed = False
    sheet_paths = sorted(
        name for name in entries if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )

    for sheet_path in sheet_paths:
        rel_path = sheet_path.replace("/worksheets/", "/worksheets/_rels/") + ".rels"
        if rel_path not in entries:
            continue
        rels_xml = entries[rel_path].decode("utf-8")
        drawing_rel_id = None
        for match in re.finditer(r"<(?:\w+:)?Relationship\b([^>]*)/>", rels_xml):
            attrs = match.group(1)
            if "relationships/drawing" not in attrs:
                continue
            id_match = re.search(r'\bId="([^"]+)"', attrs)
            if id_match:
                drawing_rel_id = id_match.group(1)
                break
        if not drawing_rel_id:
            continue

        sheet_xml = entries[sheet_path].decode("utf-8")
        canonical = f'<drawing xmlns:r="{R_NS}" r:id="{drawing_rel_id}"/>'
        if canonical in sheet_xml:
            continue

        if not re.search(r"<drawing\b", sheet_xml):
            continue

        patched = re.sub(r"<drawing\b[^>]*/>", canonical, sheet_xml, count=1)
        if 'xmlns:r="' not in patched and f'r:id="{drawing_rel_id}"' in patched:
            patched = patched.replace(
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
                (
                    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    f'xmlns:r="{R_NS}">'
                ),
                1,
            )
        if patched != sheet_xml:
            changed = True
            entries[sheet_path] = patched.encode("utf-8")

    return changed


def _strip_printer_settings_entries(entries: dict[str, bytes]) -> bool:
    """Odstraní printerSettings z mapy souborů XLSX archivu. Vrátí True pokud něco změnilo."""
    changed = False
    for name in list(entries):
        if name.startswith("xl/printerSettings/"):
            del entries[name]
            changed = True

    ct_path = "[Content_Types].xml"
    if ct_path in entries:
        ct_xml = entries[ct_path].decode("utf-8")
        patched_ct = re.sub(
            r'<Override\b[^>]*PartName="/xl/printerSettings/[^"]*"[^>]*/>\s*',
            "",
            ct_xml,
        )
        if patched_ct != ct_xml:
            changed = True
            entries[ct_path] = patched_ct.encode("utf-8")

    sheet_paths = sorted(
        name for name in entries if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )
    for sheet_path in sheet_paths:
        rel_path = sheet_path.replace("/worksheets/", "/worksheets/_rels/") + ".rels"
        if rel_path in entries:
            rels_xml = entries[rel_path].decode("utf-8")
            patched_rels = re.sub(
                r"<(?:\w+:)?Relationship\b[^>]*relationships/printerSettings[^>]*/>\s*",
                "",
                rels_xml,
            )
            if patched_rels != rels_xml:
                changed = True
                entries[rel_path] = patched_rels.encode("utf-8")

        sheet_xml = entries[sheet_path].decode("utf-8")
        patched = _strip_page_setup_printer_attrs(sheet_xml)
        if patched != sheet_xml:
            changed = True
        entries[sheet_path] = patched.encode("utf-8")

    if _repair_sheet_drawing_rids(entries):
        changed = True

    return changed


def repair_worksheet_drawings_in_xlsx(xlsx_path: Path) -> bool:
    """Opraví chybějící r:id u drawing tagů (např. po starém strip printerSettings)."""
    path = Path(xlsx_path)
    if not path.is_file():
        return False
    with zipfile.ZipFile(path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}
    if not _repair_sheet_drawing_rids(entries):
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


def strip_printer_settings_from_xlsx(xlsx_path: Path) -> bool:
    """Odstraní printerSettings a vynucený duplex z libovolného XLSX (šablona i vygenerovaný protokol)."""
    path = Path(xlsx_path)
    if not path.is_file():
        return False

    with zipfile.ZipFile(path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    if not _strip_printer_settings_entries(entries):
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


def remove_template_printer_settings(template_path: Path) -> bool:
    """Odstraní printerSettings (typicky oboustranný tisk) ze šablony."""
    return strip_printer_settings_from_xlsx(template_path)


def _next_relationship_id(rels_root: ET.Element) -> str:
    max_id = 0
    for rel in rels_root:
        rel_id = rel.get("Id") or ""
        match = re.fullmatch(r"rId(\d+)", rel_id)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return f"rId{max_id + 1}"


def _ensure_printer_settings_relationship(rels_xml: bytes) -> tuple[bytes, str]:
    root = ET.fromstring(rels_xml)
    for rel in list(root):
        if rel.get("Type") == PRINTER_SETTINGS_REL_TYPE:
            rel_id = rel.get("Id") or ""
            root.remove(rel)
            if rel_id:
                return ET.tostring(root, encoding="utf-8", xml_declaration=True), rel_id

    rel_id = _next_relationship_id(root)
    ET.SubElement(
        root,
        f"{{{PKG_REL_NS}}}Relationship",
        {
            "Type": PRINTER_SETTINGS_REL_TYPE,
            "Target": f"../printerSettings/{Path(PRINTER_SETTINGS_PART).name}",
            "Id": rel_id,
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), rel_id


def _ensure_worksheet_r_namespace(text: str) -> str:
    if re.search(
        rf'<worksheet\b[^>]*xmlns:r="{re.escape(R_NS)}"',
        text,
    ):
        return text
    return re.sub(
        r'(<worksheet\b[^>]*xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")',
        rf'\1 xmlns:r="{R_NS}"',
        text,
        count=1,
    )


def _patch_page_setup(sheet_xml: bytes, rel_id: str) -> bytes:
    text = sheet_xml.decode("utf-8")
    text = _ensure_worksheet_r_namespace(text)

    def _page_setup_attrs(raw_attrs: str) -> str:
        attrs = re.sub(r'\s*r:id="[^"]*"', "", raw_attrs)
        attrs = re.sub(r'\s*usePrinterDefaults="[^"]*"', "", attrs)
        attrs = attrs.rstrip()
        if attrs and not attrs.startswith(" "):
            attrs = f" {attrs}"
        return f'<pageSetup{attrs} r:id="{rel_id}" usePrinterDefaults="0"/>'

    if re.search(r"<pageSetup\b", text):
        text, count = re.subn(
            r"<pageSetup\b([^>]*)/>",
            lambda m: _page_setup_attrs(m.group(1)),
            text,
            count=1,
        )
        if count == 0:
            text, count = re.subn(
                r"<pageSetup\b([^>]*)>.*?</pageSetup>",
                lambda m: _page_setup_attrs(m.group(1)),
                text,
                count=1,
                flags=re.DOTALL,
            )
        if count == 0:
            raise ValueError("pageSetup tag not patched")
    else:
        text = text.replace(
            "</worksheet>",
            f'<pageSetup r:id="{rel_id}" usePrinterDefaults="0"/></worksheet>',
            1,
        )
    return text.encode("utf-8")


def _ensure_content_types(content_types_xml: bytes) -> bytes:
    root = ET.fromstring(content_types_xml)
    part_name = f"/{PRINTER_SETTINGS_PART}"
    for node in root:
        if node.get("PartName") == part_name:
            return content_types_xml
    ET.SubElement(
        root,
        f"{{{CT_NS}}}Override",
        {
            "PartName": part_name,
            "ContentType": PRINTER_SETTINGS_CONTENT_TYPE,
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def apply_printer_settings_blob(xlsx_path: Path, printer_blob: bytes) -> bool:
    """Doplní printerSettings blob ke všem listům výstupu."""
    if not printer_blob:
        return False

    xlsx_path = Path(xlsx_path)
    if not xlsx_path.is_file():
        return False

    with zipfile.ZipFile(xlsx_path, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    vba_entries = {
        name: data
        for name, data in entries.items()
        if name == VBA_PROJECT_PART or name.startswith(_VBA_ARCHIVE_PREFIXES)
    }

    sheet_paths = sorted(
        name
        for name in entries
        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)
    )
    if not sheet_paths:
        return False

    entries[PRINTER_SETTINGS_PART] = printer_blob
    entries["[Content_Types].xml"] = _ensure_content_types(entries["[Content_Types].xml"])

    for sheet_path in sheet_paths:
        rel_path = sheet_path.replace("/worksheets/", "/worksheets/_rels/") + ".rels"
        rels_xml = entries.get(rel_path)
        if rels_xml is None:
            rels_xml = (
                f'<Relationships xmlns="{PKG_REL_NS}"></Relationships>'.encode("utf-8")
            )
        patched_rels, rel_id = _ensure_printer_settings_relationship(rels_xml)
        entries[rel_path] = patched_rels
        entries[sheet_path] = _patch_page_setup(entries[sheet_path], rel_id)

    fd, temp_name = tempfile.mkstemp(suffix=".xlsx")
    try:
        import os

        os.close(fd)
        temp_path = Path(temp_name)
        for name, data in vba_entries.items():
            entries[name] = data
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
            for name, data in entries.items():
                target.writestr(name, data)
        shutil.move(str(temp_path), str(xlsx_path))
        validate_generated_xlsx(xlsx_path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise

    return True


def apply_protocol_printer_settings(xlsx_path: Path, template_path: Path) -> bool:
    """Doplní printerSettings ze šablony ke všem listům výstupu. Vrátí True pokud bylo co aplikovat."""
    printer_blob = read_template_printer_settings(template_path)
    if not printer_blob:
        return False
    return apply_printer_settings_blob(xlsx_path, printer_blob)


PROTOCOL_PRINT_SETUP_WARNING = (
    "Jednostranný tisk v protokolu nebyl doplněn. Na PC s MS Excel spusťte: "
    "python manage.py prepare_jizda_simplex_template"
)

PROTOCOL_SIMPLEX_BLOB_MISSING = (
    "Jednostranný tisk nebyl vložen — šablona jizda.xlsx nemá printerSettings. "
    "Na PC s Excelem nebo ovladačem RICOH spusťte: python manage.py prepare_jizda_simplex_template "
    "a commitněte jizda.xlsx do gitu (server pak kopíruje nastavení automaticky)."
)

PROTOCOL_SIMPLEX_DUPLEX_IN_TEMPLATE = (
    "Šablona jizda.xlsx obsahuje oboustranný tisk (printerSettings). "
    "Spusťte: python manage.py prepare_jizda_simplex_template a commitněte jizda.xlsx."
)


def ensure_protocol_simplex_print_settings(xlsx_path: Path, template_path: Path) -> str | None:
    """Strip duplex, landscape pageSetup; simplex blob jen ze šablony (bez fallback .bin)."""
    from waste_docs.services.reports.protocol_page_setup_xlsx import ensure_protocol_page_setup_in_xlsx
    from waste_docs.services.reports.simplex_printer_blob import (
        is_duplex_printer_settings_blob,
        resolve_simplex_blob_from_template,
    )

    strip_printer_settings_from_xlsx(xlsx_path)
    ensure_protocol_page_setup_in_xlsx(xlsx_path)
    template_blob = read_template_printer_settings(template_path)
    if template_blob and is_duplex_printer_settings_blob(template_blob):
        return PROTOCOL_SIMPLEX_DUPLEX_IN_TEMPLATE
    simplex_blob = resolve_simplex_blob_from_template(template_blob)
    if simplex_blob:
        apply_printer_settings_blob(xlsx_path, simplex_blob)
        return None
    return PROTOCOL_SIMPLEX_BLOB_MISSING


def ensure_protocol_print_settings(xlsx_path: Path, template_path: Path) -> tuple[bool, str | None]:
    """
    Zkopíruje printerSettings ze šablony do vygenerovaného protokolu (openpyxl je při ukládání zahazuje).

    Vrací (úspěch, varování). Varování jen pokud šablona printerSettings má, ale kopie selže.
    """
    if not template_has_printer_settings(template_path):
        return True, None
    if apply_protocol_printer_settings(xlsx_path, template_path):
        return True, None
    return False, PROTOCOL_PRINT_SETUP_WARNING
