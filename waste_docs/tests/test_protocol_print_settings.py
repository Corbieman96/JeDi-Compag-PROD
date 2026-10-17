from __future__ import annotations

import re
import struct
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from waste_docs.models import Pruvodka
from waste_docs.services.reports.protocol_print_settings import (
    VBA_PROJECT_PART,
    PROTOCOL_PRINT_SETUP_WARNING,
    PROTOCOL_SIMPLEX_BLOB_MISSING,
    PROTOCOL_SIMPLEX_DUPLEX_IN_TEMPLATE,
    apply_protocol_printer_settings,
    ensure_protocol_print_settings,
    ensure_protocol_simplex_print_settings,
    read_template_printer_settings,
    resolve_protocol_template_path,
    should_keep_vba_for_template,
    repair_worksheet_drawings_in_xlsx,
    strip_printer_settings_from_xlsx,
    template_has_printer_settings,
    template_has_vba_project,
)
from waste_docs.services.ride_protocol_xlsx import generate_protocol_xlsx

FAKE_PRINTER_BLOB = b"DEVMODE-DUPLEX-TEST-BLOB"
FAKE_VBA_BLOB = b"FAKE-VBA-TEST-BLOB"
VBA_PROJECT_REL = "http://schemas.microsoft.com/office/2006/relationships/vbaProject"


def _make_trusted_test_simplex_blob(size: int = 512) -> bytes:
    buf = bytearray(size)
    struct.pack_into("<H", buf, 68, 220)
    struct.pack_into("<H", buf, 70, max(0, size - 220))
    struct.pack_into("<I", buf, 72, 0x1003)
    struct.pack_into("<H", buf, 76, 2)
    struct.pack_into("<H", buf, 94, 1)
    return bytes(buf)


TRUSTED_TEST_SIMPLEX_BLOB = _make_trusted_test_simplex_blob()


def _make_duplex_test_blob(size: int = 512) -> bytes:
    buf = bytearray(_make_trusted_test_simplex_blob(size))
    struct.pack_into("<H", buf, 94, 2)
    return bytes(buf)


def _build_template_with_printer_settings(
    base_xlsx: Path, target: Path, *, blob: bytes | None = None
) -> None:
    printer_blob = blob if blob is not None else FAKE_PRINTER_BLOB
    with zipfile.ZipFile(base_xlsx, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    entries["xl/printerSettings/printerSettings1.bin"] = printer_blob
    rel_path = "xl/worksheets/_rels/sheet1.xml.rels"
    rels = entries[rel_path].decode()
    if PRINTER_SETTINGS_REL not in rels:
        rels = rels.replace(
            "</Relationships>",
            (
                '<Relationship Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/printerSettings" '
                'Target="../printerSettings/printerSettings1.bin" Id="rId2" />'
                "</Relationships>"
            ),
        )
        entries[rel_path] = rels.encode("utf-8")
    ct = entries["[Content_Types].xml"].decode()
    if "printerSettings1.bin" not in ct:
        ct = ct.replace(
            "</Types>",
            (
                '<Override PartName="/xl/printerSettings/printerSettings1.bin" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.printerSettings"/>'
                "</Types>"
            ),
        )
        entries["[Content_Types].xml"] = ct.encode("utf-8")

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, data in entries.items():
            out.writestr(name, data)


PRINTER_SETTINGS_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/printerSettings"
)


def _build_template_with_vba(base_xlsx: Path, target: Path) -> None:
    with zipfile.ZipFile(base_xlsx, "r") as source:
        entries = {info.filename: source.read(info.filename) for info in source.infolist()}

    entries[VBA_PROJECT_PART] = FAKE_VBA_BLOB
    ct = entries["[Content_Types].xml"].decode()
    if "vbaProject.bin" not in ct:
        ct = ct.replace(
            "</Types>",
            (
                '<Override PartName="/xl/vbaProject.bin" '
                'ContentType="application/vnd.ms-office.vbaProject"/>'
                "</Types>"
            ),
        )
        entries["[Content_Types].xml"] = ct.encode("utf-8")

    rel_path = "xl/_rels/workbook.xml.rels"
    rels = entries[rel_path].decode()
    if VBA_PROJECT_REL not in rels:
        rels = rels.replace(
            "</Relationships>",
            (
                f'<Relationship Type="{VBA_PROJECT_REL}" '
                'Target="vbaProject.bin" Id="rId99" />'
                "</Relationships>"
            ),
        )
        entries[rel_path] = rels.encode("utf-8")

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as out:
        for name, data in entries.items():
            out.writestr(name, data)


class ProtocolPrintSettingsTests(TestCase):
    def test_resolve_prefers_xlsx_over_xlsm(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            xlsx = tmp_path / "jizda.xlsx"
            xlsm = tmp_path / "jizda.xlsm"
            xlsx.write_bytes(base_template.read_bytes())
            xlsm.write_bytes(base_template.read_bytes())

            with override_settings(BASE_DIR=tmp_path):
                resolved = resolve_protocol_template_path()
            self.assertEqual(resolved, xlsx)

    def test_should_not_keep_vba_without_vba_project(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")
        self.assertFalse(should_keep_vba_for_template(template_path))

    def test_patch_page_setup_preserves_self_closing_tag(self):
        from waste_docs.services.reports.protocol_print_settings import _patch_page_setup

        sheet_xml = (
            b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            b'<pageSetup orientation="landscape" paperSize="9" fitToHeight="0" />'
            b'<drawing r:id="rId1"/></worksheet>'
        )
        patched = _patch_page_setup(sheet_xml, "rId9").decode("utf-8")
        self.assertIn('usePrinterDefaults="0"', patched)
        self.assertIn('r:id="rId9"', patched)
        self.assertRegex(patched, r"<pageSetup[^>]*/>")
        self.assertNotIn("/ r:id", patched)

    def test_template_without_printer_settings_is_noop(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")
        self.assertFalse(template_has_printer_settings(template_path))
        self.assertIsNone(read_template_printer_settings(template_path))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.xlsx"
            shutil_copy_jizda(out, template_path)
            self.assertFalse(apply_protocol_printer_settings(out, template_path))
            with zipfile.ZipFile(out) as archive:
                self.assertFalse(any("printerSettings" in n for n in archive.namelist()))

    def test_apply_adds_printer_settings_to_all_sheets(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            duplex_template = tmp_path / "jizda_duplex.xlsx"
            _build_template_with_printer_settings(template_path, duplex_template)
            self.assertTrue(template_has_printer_settings(duplex_template))

            out = tmp_path / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)
            with zipfile.ZipFile(out, "r") as source:
                entries = {info.filename: source.read(info.filename) for info in source.infolist()}
            entries["xl/worksheets/sheet2.xml"] = entries["xl/worksheets/sheet1.xml"]
            entries["xl/worksheets/_rels/sheet2.xml.rels"] = entries["xl/worksheets/_rels/sheet1.xml.rels"]
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name, data in entries.items():
                    target.writestr(name, data)

            self.assertTrue(apply_protocol_printer_settings(out, duplex_template))

            with zipfile.ZipFile(out) as archive:
                names = archive.namelist()
                self.assertIn("xl/printerSettings/printerSettings1.bin", names)
                self.assertEqual(archive.read("xl/printerSettings/printerSettings1.bin"), FAKE_PRINTER_BLOB)
                for sheet in ("sheet1.xml", "sheet2.xml"):
                    rels = archive.read(f"xl/worksheets/_rels/{sheet}.rels").decode()
                    self.assertIn(PRINTER_SETTINGS_REL, rels)
                    sheet_xml = archive.read(f"xl/worksheets/{sheet}").decode()
                    self.assertIn('usePrinterDefaults="0"', sheet_xml)
                    self.assertRegex(sheet_xml, r'r:id="rId\d+"')

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generate_protocol_landscape_without_trusted_blob(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx(
                        [ride],
                        scope="day",
                        selected_date=date(2026, 6, 10),
                    )
            with zipfile.ZipFile(path) as archive:
                self.assertFalse(any("printerSettings" in n for n in archive.namelist()))
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                self.assertIn('orientation="landscape"', sheet_xml)
                self.assertNotIn("usePrinterDefaults", sheet_xml)
            from openpyxl import load_workbook

            wb = load_workbook(path)
            try:
                self.assertEqual(wb.active.page_setup.orientation, "landscape")
            finally:
                wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generate_protocol_injects_simplex_from_template(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            simplex_template = media / "jizda_simplex.xlsx"
            _build_template_with_printer_settings(
                base_template, simplex_template, blob=TRUSTED_TEST_SIMPLEX_BLOB
            )
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx(
                        [ride],
                        template_path=simplex_template,
                        scope="day",
                        selected_date=date(2026, 6, 10),
                    )
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                self.assertIn("xl/printerSettings/printerSettings1.bin", names)
                blob = archive.read("xl/printerSettings/printerSettings1.bin")
                from waste_docs.services.reports.simplex_printer_blob import (
                    is_simplex_template_blob,
                )

                self.assertTrue(is_simplex_template_blob(blob))
                rels = archive.read("xl/worksheets/_rels/sheet1.xml.rels").decode()
                self.assertIn(PRINTER_SETTINGS_REL, rels)
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                self.assertIn('usePrinterDefaults="0"', sheet_xml)
                self.assertIn('orientation="landscape"', sheet_xml)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generate_protocol_never_injects_fallback_bin(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    with patch(
                        "waste_docs.services.reports.simplex_printer_blob.read_trusted_simplex_blob_file",
                        return_value=TRUSTED_TEST_SIMPLEX_BLOB,
                    ):
                        path = generate_protocol_xlsx(
                            [ride],
                            scope="day",
                            selected_date=date(2026, 6, 10),
                        )
            with zipfile.ZipFile(path) as archive:
                self.assertFalse(any("printerSettings" in n for n in archive.namelist()))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generate_protocol_skips_duplex_template_blob(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            blob_template = media / "jizda_duplex.xlsx"
            _build_template_with_printer_settings(
                base_template, blob_template, blob=_make_duplex_test_blob()
            )
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx(
                        [ride],
                        template_path=blob_template,
                        scope="day",
                        selected_date=date(2026, 6, 10),
                    )
            with zipfile.ZipFile(path) as archive:
                self.assertFalse(any("printerSettings" in n for n in archive.namelist()))
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                self.assertIn('orientation="landscape"', sheet_xml)
                self.assertNotIn("usePrinterDefaults", sheet_xml)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generate_protocol_preserves_template_vba(self):
        base_template = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not base_template.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            vba_template = media / "jizda_vba.xlsx"
            _build_template_with_vba(base_template, vba_template)
            self.assertTrue(template_has_vba_project(vba_template))

            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    with patch(
                        "waste_docs.services.reports.protocol_print_settings.read_template_printer_settings",
                        return_value=None,
                    ):
                        path = generate_protocol_xlsx(
                            [ride],
                            template_path=vba_template,
                            scope="day",
                            selected_date=date(2026, 6, 10),
                        )
            with zipfile.ZipFile(path) as archive:
                self.assertIn(VBA_PROJECT_PART, archive.namelist())
                self.assertEqual(archive.read(VBA_PROJECT_PART), FAKE_VBA_BLOB)


class EnsureProtocolPrintSettingsTests(TestCase):
    def test_strip_preserves_drawing_relationship_id(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            copy_path = tmp_path / "copy.xlsx"
            shutil_copy_jizda(copy_path, template_path)
            repair_worksheet_drawings_in_xlsx(copy_path)
            strip_printer_settings_from_xlsx(copy_path)
            repair_worksheet_drawings_in_xlsx(copy_path)

            with zipfile.ZipFile(copy_path) as archive:
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                rels = archive.read("xl/worksheets/_rels/sheet1.xml.rels").decode()
                self.assertIn('relationships/drawing', rels)
                id_match = re.search(r'Id="(rId\d+)"', rels)
                self.assertIsNotNone(id_match)
                self.assertIn(f'r:id="{id_match.group(1)}"', sheet_xml)

    def test_strip_removes_printer_settings_blob(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            blob_template = tmp_path / "jizda_blob.xlsx"
            _build_template_with_printer_settings(template_path, blob_template)
            self.assertTrue(strip_printer_settings_from_xlsx(blob_template))
            self.assertFalse(template_has_printer_settings(blob_template))

    def test_uses_template_blob_when_available(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            duplex_template = tmp_path / "jizda_duplex.xlsx"
            _build_template_with_printer_settings(template_path, duplex_template)
            out = tmp_path / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)

            ok, warn = ensure_protocol_print_settings(out, duplex_template)
            self.assertTrue(ok)
            self.assertIsNone(warn)

    def test_ensure_simplex_applies_template_blob_when_simplex(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        from waste_docs.services.reports.simplex_printer_blob import is_simplex_template_blob

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            simplex_template = tmp_path / "jizda_simplex.xlsx"
            _build_template_with_printer_settings(
                template_path, simplex_template, blob=TRUSTED_TEST_SIMPLEX_BLOB
            )
            out = tmp_path / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)
            warn = ensure_protocol_simplex_print_settings(out, simplex_template)
            self.assertIsNone(warn)
            self.assertTrue(template_has_printer_settings(out))
            with zipfile.ZipFile(out) as archive:
                blob = archive.read("xl/printerSettings/printerSettings1.bin")
                self.assertTrue(is_simplex_template_blob(blob))
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                self.assertIn('orientation="landscape"', sheet_xml)

    def test_ensure_simplex_rejects_duplex_template(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            duplex_template = tmp_path / "jizda_duplex.xlsx"
            _build_template_with_printer_settings(
                template_path, duplex_template, blob=_make_duplex_test_blob()
            )
            out = tmp_path / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)
            warn = ensure_protocol_simplex_print_settings(out, duplex_template)
            self.assertEqual(warn, PROTOCOL_SIMPLEX_DUPLEX_IN_TEMPLATE)
            self.assertFalse(template_has_printer_settings(out))

    def test_ensure_simplex_without_blob_keeps_landscape_only(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)
            warn = ensure_protocol_simplex_print_settings(out, template_path)
            self.assertEqual(warn, PROTOCOL_SIMPLEX_BLOB_MISSING)
            self.assertFalse(template_has_printer_settings(out))
            with zipfile.ZipFile(out) as archive:
                sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode()
                self.assertIn('orientation="landscape"', sheet_xml)

    def test_resolve_trusted_simplex_prefers_template_over_fallback_file(self):
        from waste_docs.services.reports.simplex_printer_blob import resolve_trusted_simplex_blob

        template_blob = _make_trusted_test_simplex_blob(600)
        fallback_blob = _make_trusted_test_simplex_blob(700)
        fallback_blob = bytes(fallback_blob[:512]) + b"FALLBACK-MARKER" + bytes(fallback_blob[524:])

        with patch(
            "waste_docs.services.reports.simplex_printer_blob.read_trusted_simplex_blob_file",
            return_value=fallback_blob,
        ):
            resolved = resolve_trusted_simplex_blob(template_blob)
        self.assertEqual(resolved, template_blob)

    def test_noop_when_template_has_no_printer_settings(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)

            ok, warn = ensure_protocol_print_settings(out, template_path)
            self.assertTrue(ok)
            self.assertIsNone(warn)

    def test_returns_warning_when_apply_fails_with_duplex_template(self):
        template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
        if not template_path.is_file():
            self.skipTest("jizda.xlsx není v kořeni projektu")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            duplex_template = tmp_path / "jizda_duplex.xlsx"
            _build_template_with_printer_settings(template_path, duplex_template)
            out = tmp_path / "protokol.xlsx"
            shutil_copy_jizda(out, template_path)

            with patch(
                "waste_docs.services.reports.protocol_print_settings.apply_protocol_printer_settings",
                return_value=False,
            ):
                ok, warn = ensure_protocol_print_settings(out, duplex_template)
            self.assertFalse(ok)
            self.assertEqual(warn, PROTOCOL_PRINT_SETUP_WARNING)


def shutil_copy_jizda(target: Path, source: Path) -> None:
    import shutil

    shutil.copyfile(source, target)
