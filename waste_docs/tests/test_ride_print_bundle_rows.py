from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from waste_docs.models import Pruvodka
from waste_docs.services.ride_bulk_actions import (
    append_day_protocol_file,
    append_protocol_and_supplement_file_rows,
    build_print_rows_and_files,
    delete_protocol_files_for_rides,
)
from waste_docs.services.ride_protocol_xlsx import PROTOCOL_SCOPE_GROUP


class RidePrintBundleFileRowTests(TestCase):
    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=True)
    def test_file_rows_include_rz_and_driver_from_ride(self, _mock_has_excel):
        ride = Pruvodka(
            pk=42,
            snd_cislo_listu="",
            drive_date=date(2026, 6, 8),
            vehicle_rz_snapshot="1P23456",
            driver_snapshot="Jan Novák",
            name_snapshot="Firma ABC s.r.o.",
            waste_type_snapshot="Komunální odpad směsný",
        )
        ride.generated_file = MagicMock()
        ride.generated_file.name = "pruvodky/test.xlsx"
        ride.generated_file.url = "/media/pruvodky/test.xlsx"
        ride.generated_file.path = "/tmp/pruvodky/test.xlsx"

        _, file_rows, _ = build_print_rows_and_files([ride])

        self.assertEqual(len(file_rows), 1)
        self.assertEqual(file_rows[0]["kind"], "xlsx")
        self.assertEqual(file_rows[0]["vehicle_rz"], "1P23456")
        self.assertEqual(file_rows[0]["driver"], "Jan Novák")
        self.assertEqual(file_rows[0]["kdo"], "Firma ABC s.r.o.")
        self.assertEqual(file_rows[0]["odpad"], "Komunální odpad směsný")

    @patch("waste_docs.services.ride_bulk_actions.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.services.ride_bulk_actions.display_zpo_file_for_pruvodka")
    @patch("waste_docs.services.ride_bulk_actions.effective_zpo_file")
    @patch("waste_docs.services.ride_bulk_actions.system_may_generate_zpo_instance", return_value=False)
    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=False)
    @patch("waste_docs.services.ride_bulk_actions.pair_docs_for_pruvodka")
    def test_build_print_rows_includes_existing_zpo_when_generation_blocked(
        self,
        mock_pair_docs,
        _mock_excel,
        _mock_may,
        mock_effective_zpo,
        mock_display_zpo,
        mock_ensure,
    ):
        ride = Pruvodka(
            pk=1195,
            snd_cislo_listu="0000491-2026-6",
            drive_date=date(2026, 6, 26),
            vehicle_rz_snapshot="9S57595",
            driver_snapshot="David Nejdedlo",
        )
        mock_pair_docs.return_value = MagicMock()
        mock_effective_zpo.return_value = None
        zpo_file = MagicMock(url="/media/zpo/instance_1195.pdf", path="/tmp/zpo/instance_1195.pdf")
        mock_display_zpo.return_value = zpo_file

        _, file_rows, warnings = build_print_rows_and_files([ride], include_pio=False)

        mock_ensure.assert_not_called()
        self.assertEqual(len(file_rows), 1)
        self.assertEqual(file_rows[0]["kind"], "zpo")
        self.assertEqual(file_rows[0]["url"], "/media/zpo/instance_1195.pdf")
        self.assertEqual(warnings, [])

    @patch("waste_docs.services.ride_bulk_actions.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.services.ride_bulk_actions.display_zpo_file_for_pruvodka")
    @patch("waste_docs.services.ride_bulk_actions.effective_zpo_file")
    @patch("waste_docs.services.ride_bulk_actions.system_may_generate_zpo_instance", return_value=True)
    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=False)
    @patch("waste_docs.services.ride_bulk_actions.pair_docs_for_pruvodka")
    def test_build_print_rows_ensures_missing_zpo_instance(
        self,
        mock_pair_docs,
        _mock_excel,
        _mock_may,
        mock_effective_zpo,
        mock_display_zpo,
        mock_ensure,
    ):
        from catalogs.models import (
            ActivityCatalog,
            AddressCatalog,
            IcoCatalog,
            NameCatalog,
            SuffixCatalog,
            VehicleRzCatalog,
            WasteCategoryCatalog,
            WasteCodeCatalog,
            WasteTypeCatalog,
        )
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user("zpo_print", password="pw")
        activity = ActivityCatalog.objects.create(name="Svoz ZPO print")
        ride = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="Subjekt ZPO print"),
            ico=IcoCatalog.objects.create(value="11223355"),
            address=AddressCatalog.objects.create(value="Adr ZPO"),
            waste_type=WasteTypeCatalog.objects.create(code="880088", value="Wzpo"),
            waste_code=WasteCodeCatalog.objects.create(value="WCZP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOZP"),
            suffix=SuffixCatalog.objects.create(value="SFXZP"),
            activity=activity,
            drive_date=date(2026, 6, 26),
            vehicle_rz=VehicleRzCatalog.objects.create(value="9S57595"),
            snd_cislo_listu="0000491-2026-6",
            container_number="",
            created_by=user,
        )
        mock_pair = MagicMock()
        mock_pair_docs.return_value = mock_pair
        mock_effective_zpo.return_value = MagicMock()
        zpo_file = MagicMock(url="/media/zpo/instance.pdf", path="/tmp/zpo/instance.pdf")
        mock_display_zpo.side_effect = [None, zpo_file]

        _, file_rows, warnings = build_print_rows_and_files([ride], include_pio=False)

        mock_ensure.assert_called_once_with(ride.pk)
        self.assertEqual(len(file_rows), 1)
        self.assertEqual(file_rows[0]["kind"], "zpo")
        self.assertEqual(file_rows[0]["url"], "/media/zpo/instance.pdf")
        self.assertEqual(warnings, [])

    @patch("waste_docs.services.ride_bulk_actions.effective_pio_file")
    @patch("waste_docs.services.ride_bulk_actions.system_may_generate_zpo_instance", return_value=False)
    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=False)
    def test_include_pio_false_skips_pio_rows(self, _mock_excel, _mock_zpo, mock_pio):
        mock_pio.return_value = MagicMock(url="/media/pio/test.pdf", name="pio/test.pdf", path="/tmp/pio/test.pdf")
        ride = Pruvodka(pk=99, snd_cislo_listu="", drive_date=date(2026, 6, 8))
        _, file_rows, _ = build_print_rows_and_files([ride], include_pio=False)
        self.assertEqual(file_rows, [])
        mock_pio.assert_not_called()

    @patch("waste_docs.services.ride_bulk_actions.effective_pio_file")
    @patch("waste_docs.services.ride_bulk_actions.system_may_generate_zpo_instance", return_value=False)
    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=False)
    def test_include_pio_true_adds_pio_row(self, _mock_excel, _mock_zpo, mock_pio):
        mock_pio.return_value = MagicMock(url="/media/pio/test.pdf", name="pio/test.pdf", path="/tmp/pio/test.pdf")
        ride = Pruvodka(pk=100, snd_cislo_listu="", drive_date=date(2026, 6, 8))
        _, file_rows, _ = build_print_rows_and_files([ride], include_pio=True)
        self.assertEqual(len(file_rows), 1)
        self.assertEqual(file_rows[0]["kind"], "pio")

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_protocol_row_has_empty_rz_and_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            protocol_dir = media / "protokoly"
            protocol_dir.mkdir(parents=True)
            (protocol_dir / "protokol_0000100-2026.pdf").write_bytes(b"%PDF")

            ride = Pruvodka(
                pk=1,
                snd_cislo_listu="0000100-2026",
                drive_date=date(2026, 6, 8),
                vehicle_rz_snapshot="1P23456",
                driver_snapshot="Jan Novák",
            )

            with override_settings(MEDIA_ROOT=media):
                file_rows = append_day_protocol_file(
                    [],
                    [ride],
                    date(2026, 6, 8),
                    generate_if_missing=False,
                )

            self.assertEqual(len(file_rows), 1)
            self.assertEqual(file_rows[0]["kind"], "protocol")
            self.assertTrue(file_rows[0]["path"].endswith(".pdf"))
            self.assertTrue(file_rows[0]["url"].endswith(".pdf"))
            self.assertEqual(file_rows[0]["vehicle_rz"], "")
            self.assertEqual(file_rows[0]["driver"], "")
            self.assertEqual(file_rows[0]["kdo"], "")
            self.assertEqual(file_rows[0]["odpad"], "")

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_group_protocol_not_auto_created_when_missing(self):
        ride = Pruvodka(
            pk=1,
            snd_cislo_listu="0000316-2026-1",
            drive_date=date(2026, 6, 12),
            vehicle_rz_id=99,
            vehicle_rz_snapshot="8S46830",
        )
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media):
                rows = append_protocol_and_supplement_file_rows(
                    [],
                    [ride],
                    date(2026, 6, 12),
                    scope=PROTOCOL_SCOPE_GROUP,
                    generate_if_missing=False,
                )
            self.assertEqual(rows, [])

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_group_protocol_delete_removes_legacy_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            protocol_dir = media / "protokoly"
            protocol_dir.mkdir(parents=True)
            legacy = protocol_dir / "protokol_0000316-2026-1.xlsx"
            pdf = protocol_dir / "protokol_0000316-2026-1.pdf"
            legacy.write_bytes(b"xlsx")
            pdf.write_bytes(b"%PDF")
            ride = Pruvodka(
                pk=1,
                snd_cislo_listu="0000316-2026-1",
                drive_date=date(2026, 6, 12),
                vehicle_rz_id=99,
            )
            with override_settings(MEDIA_ROOT=media):
                deleted = delete_protocol_files_for_rides(
                    [ride],
                    scope=PROTOCOL_SCOPE_GROUP,
                    selected_date=date(2026, 6, 12),
                )
            self.assertEqual(deleted, 2)
            self.assertFalse(legacy.exists())
            self.assertFalse(pdf.exists())
