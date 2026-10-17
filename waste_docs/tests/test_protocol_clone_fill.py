from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from waste_docs.models import Pruvodka
from waste_docs.services.reports.protocol_fill_sheet import PROTOCOL_KDE_LABEL_COORDS, PROTOCOL_LINE_BLOCK_ROWS
from waste_docs.services.reports.protocol_sheet_bounds import PROTOCOL_SHEET_MAX_ROW, trim_protocol_sheet_to_bounds
from waste_docs.services.ride_protocol_xlsx import (
    PROTOCOL_LINES_PER_SHEET,
    PROTOCOL_STATIC_LABEL_COORDS,
    _page_snd_header,
    build_protocol_pages,
    generate_protocol_xlsx,
)

PROTOCOL_LAYOUT_MAX_ROW = PROTOCOL_SHEET_MAX_ROW
PROTOCOL_TEMPLATE_MAX_COL = 13


def _template_sheet():
    template_path = Path(settings.BASE_DIR) / "jizda.xlsx"
    if not template_path.is_file():
        return None, None
    from openpyxl import load_workbook

    wb = load_workbook(template_path)
    trim_protocol_sheet_to_bounds(wb.active)
    return wb, wb.active


def _template_row_heights(tpl_sheet) -> dict[int, float | None]:
    return {row: tpl_sheet.row_dimensions[row].height for row in range(1, PROTOCOL_LAYOUT_MAX_ROW + 1)}


def _template_column_widths(tpl_sheet) -> dict[str, float | None]:
    from openpyxl.utils import get_column_letter

    return {
        get_column_letter(col): tpl_sheet.column_dimensions[get_column_letter(col)].width
        for col in range(1, PROTOCOL_TEMPLATE_MAX_COL + 1)
    }


def _assert_sheet_grid_matches_template(test_case, sheet, tpl_sheet) -> None:
    tpl_heights = _template_row_heights(tpl_sheet)
    tpl_widths = _template_column_widths(tpl_sheet)
    for row_num in range(1, PROTOCOL_LAYOUT_MAX_ROW + 1):
        expected = tpl_heights.get(row_num)
        if expected is None:
            continue
        test_case.assertFalse(sheet.row_dimensions[row_num].hidden, f"row {row_num} hidden")
        test_case.assertEqual(
            sheet.row_dimensions[row_num].height,
            expected,
            f"row {row_num}",
        )
    for letter, expected in tpl_widths.items():
        if expected is None:
            continue
        test_case.assertEqual(
            sheet.column_dimensions[letter].width,
            expected,
            f"col {letter}",
        )
    test_case.assertEqual(len(sheet.merged_cells.ranges), len(tpl_sheet.merged_cells.ranges))
    test_case.assertEqual(sheet.page_setup.fitToHeight, tpl_sheet.page_setup.fitToHeight)
    test_case.assertEqual(sheet.page_setup.fitToWidth, tpl_sheet.page_setup.fitToWidth)
    test_case.assertEqual(sheet.page_setup.orientation, tpl_sheet.page_setup.orientation)
    out_area = (sheet.print_area or "").replace("'", "").replace("$", "")
    test_case.assertIn("A1:M38", out_area)
    tpl_area = (tpl_sheet.print_area or "").replace("'", "").replace("$", "")
    if tpl_area:
        out_range = out_area.split("!")[-1] if "!" in out_area else out_area
        tpl_range = tpl_area.split("!")[-1] if "!" in tpl_area else tpl_area
        test_case.assertEqual(out_range, tpl_range)
    test_case.assertEqual(sheet["C5"].alignment.wrap_text, tpl_sheet["C5"].alignment.wrap_text)


class ProtocolCloneFillTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_all_sheets_identical_to_template_except_tokens(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        rides = [
            Pruvodka(
                pk=i,
                snd_cislo_listu=f"0001{i:03d}-2026-1",
                drive_date=date(2026, 6, 20),
                vehicle_rz_id=100 + i,
                vehicle_rz_snapshot=f"8S{i:04d}",
                driver_snapshot=f"Ridic{i}",
                name_snapshot=f"Subjekt {i}",
            )
            for i in range(1, 21)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    with patch(
                        "waste_docs.services.ride_protocol_xlsx.ensure_protocol_simplex_print_settings",
                    ):
                        path = generate_protocol_xlsx(
                            rides,
                            scope="day",
                            selected_date=date(2026, 6, 20),
                        )

            from openpyxl import load_workbook

            wb = load_workbook(path)
            data_sheets = [wb[n] for n in wb.sheetnames if n != "Poznamky"]
            self.assertEqual(len(data_sheets), 20)
            for idx in (0, 9, 19):
                _assert_sheet_grid_matches_template(self, data_sheets[idx], tpl_sheet)
                self.assertEqual(data_sheets[idx].max_row, PROTOCOL_SHEET_MAX_ROW)
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_generated_sheet_has_no_rows_below_layout(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
            name_snapshot="Firma s.r.o.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx([ride], scope="day", selected_date=date(2026, 6, 10))

            from openpyxl import load_workbook

            wb = load_workbook(path)
            sheet = wb[wb.sheetnames[0]]
            self.assertEqual(sheet.max_row, PROTOCOL_SHEET_MAX_ROW)
            self.assertLessEqual(sheet.max_column, 13)
            area = (sheet.print_area or "").replace("'", "").replace("$", "")
            self.assertIn("A1:M38", area)
            self.assertEqual(sheet.page_setup.orientation, "landscape")
            for row in range(PROTOCOL_SHEET_MAX_ROW + 1, PROTOCOL_SHEET_MAX_ROW + 5):
                for col in range(1, 14):
                    self.assertIsNone(sheet.cell(row=row, column=col).value)
            wb.close()
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_eight_rides_two_sheets(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        rides = [
            Pruvodka(
                pk=i,
                snd_cislo_listu=f"0000295-2026-{i}",
                drive_date=date(2026, 6, 20),
                vehicle_rz_id=5,
                vehicle_rz_snapshot="5SB5766",
                driver_snapshot="Vrabec",
                name_snapshot=f"Jízda {i}",
            )
            for i in range(1, 9)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx(rides, scope="day", selected_date=date(2026, 6, 20))

            from openpyxl import load_workbook

            wb = load_workbook(path)
            data_sheets = [wb[n] for n in wb.sheetnames if n != "Poznamky"]
            self.assertEqual(len(data_sheets), 2)
            self.assertEqual(PROTOCOL_LINES_PER_SHEET, 7)
            self.assertIn("Jízda 1", data_sheets[0]["C5"].value or "")
            self.assertIn("Jízda 7", data_sheets[0]["C35"].value or "")
            self.assertIn("Jízda 8", data_sheets[1]["C5"].value or "")
            for sheet in data_sheets:
                _assert_sheet_grid_matches_template(self, sheet, tpl_sheet)
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_static_labels_unchanged(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")
        expected = {coord: tpl_sheet[coord].value for coord in PROTOCOL_STATIC_LABEL_COORDS}

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 10),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="5SB5766",
            driver_snapshot="Jan Vrabec",
            name_snapshot="Firma s.r.o.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx([ride], scope="day", selected_date=date(2026, 6, 10))

            from openpyxl import load_workbook

            sheet = load_workbook(path)[load_workbook(path).sheetnames[0]]
            for coord, value in expected.items():
                self.assertEqual(sheet[coord].value, value, coord)
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_single_ride_clears_unused_slots(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000295-2026-1",
            drive_date=date(2026, 6, 20),
            vehicle_rz_id=5,
            vehicle_rz_snapshot="4SK3061",
            driver_snapshot="Butnaru Ion",
            name_snapshot="Zahrada Compag",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx([ride], scope="day", selected_date=date(2026, 6, 20))

            from openpyxl import load_workbook

            sheet = load_workbook(path)[load_workbook(path).sheetnames[0]]
            _assert_sheet_grid_matches_template(self, sheet, tpl_sheet)
            self.assertEqual(sheet["C5"].value, "Zahrada Compag")
            self.assertIn(sheet["C10"].value, (None, ""))
            self.assertIn(sheet[PROTOCOL_KDE_LABEL_COORDS[1]].value, (None, ""))
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_four_rides_one_sheet(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        rides = [
            Pruvodka(
                pk=i,
                snd_cislo_listu=f"0000295-2026-{i}",
                drive_date=date(2026, 6, 20),
                vehicle_rz_id=5,
                vehicle_rz_snapshot="9S57595",
                driver_snapshot="Galit",
                name_snapshot=f"CZS subjekt {i}",
            )
            for i in range(1, 5)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    path = generate_protocol_xlsx(rides, scope="day", selected_date=date(2026, 6, 20))

            from openpyxl import load_workbook

            wb = load_workbook(path)
            data_sheets = [wb[n] for n in wb.sheetnames if n != "Poznamky"]
            self.assertEqual(len(data_sheets), 1)
            sheet = data_sheets[0]
            _assert_sheet_grid_matches_template(self, sheet, tpl_sheet)
            for line_idx in range(1, 5):
                kdo_row = PROTOCOL_LINE_BLOCK_ROWS[line_idx - 1][1]
                self.assertIn(f"CZS subjekt {line_idx}", sheet[f"C{kdo_row}"].value or "")
            self.assertIn(sheet["C25"].value, (None, ""))
        tpl_wb.close()

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_seven_driver_day_all_sheets_match_template(self):
        tpl_wb, tpl_sheet = _template_sheet()
        if tpl_sheet is None:
            self.skipTest("jizda.xlsx není v kořeni projektu")

        driver_specs = [
            ("Butnaru Ion", "4SK3061", 1),
            ("Galit", "9S57595", 4),
            ("Jarka", "8S11111", 1),
            ("Nejedlo", "4SJ5360", 2),
            ("Poliscuk", "8S22222", 1),
            ("Salac", "8S33333", 2),
        ]
        rides = []
        pk = 1
        rz_ids: dict[str, int] = {}
        for driver, rz, count in driver_specs:
            rz_id = rz_ids.setdefault(rz, len(rz_ids) + 5)
            for _i in range(count):
                rides.append(
                    Pruvodka(
                        pk=pk,
                        snd_cislo_listu=f"0000{pk}-2026-1",
                        drive_date=date(2026, 6, 20),
                        vehicle_rz_id=rz_id,
                        vehicle_rz_snapshot=rz,
                        driver_snapshot=driver,
                        name_snapshot=f"Subjekt {pk}",
                    )
                )
                pk += 1

        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media, BASE_DIR=settings.BASE_DIR):
                with patch(
                    "waste_docs.services.ride_protocol_xlsx._vehicle_kind_label",
                    return_value="Solo",
                ):
                    with patch(
                        "waste_docs.services.ride_protocol_xlsx.ensure_protocol_simplex_print_settings",
                    ):
                        path = generate_protocol_xlsx(
                            rides,
                            scope="day",
                            selected_date=date(2026, 6, 20),
                        )

            from openpyxl import load_workbook

            wb = load_workbook(path)
            data_sheets = [wb[n] for n in wb.sheetnames if n != "Poznamky"]
            self.assertEqual(len(data_sheets), 6)
            for sheet in data_sheets:
                _assert_sheet_grid_matches_template(self, sheet, tpl_sheet)
            self.assertEqual(
                data_sheets[0].row_dimensions[5].height,
                data_sheets[3].row_dimensions[5].height,
            )
        tpl_wb.close()

    def test_build_protocol_pages_dynamic_count(self):
        rides = [
            Pruvodka(
                pk=i,
                snd_cislo_listu=f"0000{i}-2026-1",
                drive_date=date(2026, 6, 20),
                vehicle_rz_id=5 if i <= 3 else 6,
                vehicle_rz_snapshot="5SB5766" if i <= 3 else "9S57595",
                driver_snapshot="Vrabec" if i <= 3 else "Galit",
            )
            for i in range(1, 6)
        ]
        pages = build_protocol_pages(rides)
        self.assertEqual(len(pages), 2)
        self.assertEqual(len(pages[0]["lines"]), 2)
        self.assertEqual(len(pages[1]["lines"]), 3)
        self.assertEqual(pages[0]["sheet_title_base"], "Galit 9S57595")
        self.assertEqual(pages[1]["sheet_title_base"], "Vrabec 5SB5766")

    def test_page_snd_header_single_group(self):
        lines = [{"snd_cislo_listu": "0000295-2026-1"}]
        self.assertEqual(_page_snd_header(lines), "0000295-2026")

    def test_page_snd_header_single_group_multiple_sequences(self):
        lines = [
            {"snd_cislo_listu": "0000295-2026-1"},
            {"snd_cislo_listu": "0000295-2026-2"},
        ]
        self.assertEqual(_page_snd_header(lines), "0000295-2026")

    def test_page_snd_header_multi_group(self):
        lines = [
            {"snd_cislo_listu": "0000493-2026-1"},
            {"snd_cislo_listu": "0000471-2026-1"},
            {"snd_cislo_listu": "0000475-2026-2"},
        ]
        self.assertEqual(_page_snd_header(lines), "493, 471, 475")

    def test_page_snd_header_dedupes_same_group(self):
        lines = [
            {"snd_cislo_listu": "0000493-2026-1"},
            {"snd_cislo_listu": "0000493-2026-2"},
            {"snd_cislo_listu": "0000471-2026-1"},
        ]
        self.assertEqual(_page_snd_header(lines), "493, 471")

    def test_page_snd_header_truncates_with_suffix(self):
        groups = [1000 + i for i in range(7)]
        lines = [{"snd_cislo_listu": f"{g:07d}-2026-1"} for g in groups]
        header = _page_snd_header(lines, max_len=30)
        self.assertLessEqual(len(header), 30)
        self.assertRegex(header, r" \+\d+$")

    def test_build_protocol_pages_snd_header_per_sheet(self):
        rides = [
            Pruvodka(
                pk=1,
                snd_cislo_listu="0000493-2026-1",
                drive_date=date(2026, 6, 26),
                vehicle_rz_id=1,
                vehicle_rz_snapshot="1AB2345",
                driver_snapshot="Hlavacek",
            ),
            Pruvodka(
                pk=2,
                snd_cislo_listu="0000471-2026-1",
                drive_date=date(2026, 6, 26),
                vehicle_rz_id=1,
                vehicle_rz_snapshot="1AB2345",
                driver_snapshot="Hlavacek",
            ),
            Pruvodka(
                pk=3,
                snd_cislo_listu="0000475-2026-1",
                drive_date=date(2026, 6, 26),
                vehicle_rz_id=1,
                vehicle_rz_snapshot="1AB2345",
                driver_snapshot="Hlavacek",
            ),
        ]
        pages = build_protocol_pages(rides)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["snd_base"], "493, 471, 475")
