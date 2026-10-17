from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.print_bundle_prepare import (
    count_rides_missing_excel,
    prepare_progress_label,
    print_prepare_context,
    ride_needs_zpo_prepare,
    rides_missing_zpo,
)
from waste_docs.zpo_instance_generator import CURRENT_ZPO_GENERATOR_REVISION


class PrintBundlePrepareTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("prepare_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_DISPECER)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2027, 5, 10)
        self.rz = VehicleRzCatalog.objects.create(value="1P77777")
        self.activity = ActivityCatalog.objects.create(name="Prepare act")
        self.ride = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="Subjekt prepare"),
            ico=IcoCatalog.objects.create(value="11223344"),
            address=AddressCatalog.objects.create(value="Adr prepare"),
            waste_type=WasteTypeCatalog.objects.create(code="770077", value="Wprepare"),
            waste_code=WasteCodeCatalog.objects.create(value="WCPR"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOPR"),
            suffix=SuffixCatalog.objects.create(value="SFXPR"),
            activity=self.activity,
            drive_date=self.drive_date,
            vehicle_rz=self.rz,
            vehicle_rz_id=self.rz.pk,
            vehicle_rz_snapshot="1P77777",
            container_number="",
            created_by=self.user,
        )

    def test_missing_excel_count_without_file(self):
        self.assertEqual(count_rides_missing_excel([self.ride]), 1)

    def test_prepare_progress_label_excel_only(self):
        self.assertEqual(
            prepare_progress_label(missing_excel_count=2, missing_zpo_count=0),
            "Generuji Excel průvodky…",
        )

    def test_print_prepare_context_when_excel_missing(self):
        ctx = print_prepare_context([self.ride])
        self.assertTrue(ctx["needs_print_prepare"])
        self.assertEqual(ctx["missing_excel_count"], 1)

    @patch("waste_docs.views.pruvodka_pages.actions.build_print_rows_and_files")
    @patch("waste_docs.views.pruvodka_pages.actions.print_prepare_context")
    def test_ride_print_bundle_get_skips_build_when_prepare_needed(self, mock_ctx, mock_build):
        mock_ctx.return_value = {
            "needs_print_prepare": True,
            "missing_excel_count": 1,
            "missing_zpo_count": 0,
            "prepare_progress_label": "Generuji Excel průvodky…",
        }
        url = (
            reverse("waste_docs:ride_print_bundle")
            + f"?date={self.drive_date.isoformat()}&vehicle_rz_id={self.rz.pk}"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        mock_build.assert_not_called()
        self.assertContains(response, "data-print-prepare-form")

    @patch("waste_docs.services.zpo_instance_staleness.effective_zpo_file")
    @patch("waste_docs.services.zpo_instance_staleness.system_may_generate_zpo_instance", return_value=True)
    def test_ride_needs_zpo_prepare_when_generator_revision_outdated(self, _mock_may, mock_zpo_file):
        mock_zpo_file.return_value = MagicMock()
        ride = self.ride
        ride.snd_cislo_listu = "0000999-2027-1"
        ride.zpo_instance_for_snd = "0000999-2027-1"
        ride.zpo_generator_revision = max(0, CURRENT_ZPO_GENERATOR_REVISION - 1)
        ride.zpo_instance_file = MagicMock()
        ride.zpo_instance_file.name = "pruvodky/zpo_instance/1_test.pdf"
        with patch("waste_docs.services.zpo_instance_staleness.default_storage.exists", return_value=True):
            self.assertTrue(ride_needs_zpo_prepare(ride))
            self.assertEqual(rides_missing_zpo([ride]), [ride])

    @patch("waste_docs.services.zpo_instance_staleness.effective_zpo_file")
    @patch("waste_docs.services.zpo_instance_staleness.system_may_generate_zpo_instance", return_value=True)
    def test_ride_needs_zpo_prepare_false_when_up_to_date(self, _mock_may, mock_zpo_file):
        mock_zpo_file.return_value = MagicMock()
        ride = self.ride
        ride.snd_cislo_listu = "0000999-2027-1"
        ride.zpo_instance_for_snd = "0000999-2027-1"
        ride.zpo_generator_revision = CURRENT_ZPO_GENERATOR_REVISION
        ride.zpo_instance_file = MagicMock()
        ride.zpo_instance_file.name = "pruvodky/zpo_instance/1_test.pdf"
        with patch("waste_docs.services.zpo_instance_staleness.default_storage.exists", return_value=True):
            self.assertFalse(ride_needs_zpo_prepare(ride))
            self.assertEqual(rides_missing_zpo([ride]), [])

    @patch("waste_docs.services.print_bundle_prepare.display_zpo_file_for_pruvodka")
    @patch("waste_docs.services.print_bundle_prepare.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.services.print_bundle_prepare.effective_zpo_file")
    @patch("waste_docs.services.zpo_instance_staleness.effective_zpo_file")
    @patch("waste_docs.services.zpo_instance_staleness.system_may_generate_zpo_instance", return_value=True)
    @patch("waste_docs.services.print_bundle_prepare.system_may_generate_zpo_instance", return_value=True)
    def test_ensure_zpo_regenerates_outdated_instance(
        self, _mock_may_eligible, _mock_may_stale, mock_zpo_stale, mock_zpo_eligible, mock_ensure, mock_display
    ):
        from waste_docs.services.print_bundle_prepare import ensure_zpo_files_for_rides

        mock_zpo_stale.return_value = MagicMock()
        mock_zpo_eligible.return_value = MagicMock()
        ride = self.ride
        ride.snd_cislo_listu = "0000999-2027-1"
        ride.zpo_instance_for_snd = "0000999-2027-1"
        ride.zpo_generator_revision = max(0, CURRENT_ZPO_GENERATOR_REVISION - 1)
        ride.zpo_instance_file = MagicMock()
        ride.zpo_instance_file.name = "pruvodky/zpo_instance/1_test.pdf"
        mock_display.return_value = ride.zpo_instance_file
        with patch("waste_docs.services.zpo_instance_staleness.default_storage.exists", return_value=True):
            generated, warnings = ensure_zpo_files_for_rides([ride])
        mock_ensure.assert_called_once_with(ride.pk)
        self.assertEqual(generated, 1)
        self.assertEqual(warnings, [])

    @patch("waste_docs.views.print_bundle_prepare.prepare_print_bundle_files")
    def test_ride_print_bundle_prepare_post(self, mock_prepare):
        mock_prepare.return_value = {"excel_generated": 1, "zpo_generated": 0, "zpo_warnings": []}
        self.ride.vehicle_rz_id = self.rz.pk
        self.ride.save(update_fields=("vehicle_rz_id",))
        url = reverse("waste_docs:ride_print_bundle_prepare")
        response = self.client.post(
            url,
            {
                "date": self.drive_date.isoformat(),
                "vehicle_rz_id": self.rz.pk,
                "next": reverse("waste_docs:ride_print_bundle")
                + f"?date={self.drive_date.isoformat()}&vehicle_rz_id={self.rz.pk}",
            },
        )
        self.assertEqual(response.status_code, 302)
        mock_prepare.assert_called_once()
