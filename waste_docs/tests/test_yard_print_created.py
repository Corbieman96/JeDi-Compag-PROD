from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
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


class YardPrintCreatedViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("yard_print_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_DISPECER)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2027, 4, 20)
        self.rz = VehicleRzCatalog.objects.create(value="9Y88888")
        self.ride = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="Subjekt yard print"),
            ico=IcoCatalog.objects.create(value="55443322"),
            address=AddressCatalog.objects.create(value="Adr yard print"),
            waste_type=WasteTypeCatalog.objects.create(code="990098", value="Wyp"),
            waste_code=WasteCodeCatalog.objects.create(value="WCYP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOYP"),
            suffix=SuffixCatalog.objects.create(value="SFXYP"),
            activity=ActivityCatalog.objects.create(name="Yard act"),
            drive_date=self.drive_date,
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="9Y88888",
            container_number="",
            created_by=self.user,
        )
        self.ride.generated_file.save(
            "yard_print_test.xlsx",
            ContentFile(b"PK"),
            save=True,
        )

    @patch("waste_docs.views.pruvodka_pages.actions.build_print_rows_and_files")
    @patch("waste_docs.views.pruvodka_pages.actions.print_prepare_context")
    def test_yard_print_created_shows_prepare_when_needed(self, mock_ctx, mock_build):
        mock_ctx.return_value = {
            "needs_print_prepare": True,
            "missing_excel_count": 1,
            "missing_zpo_count": 0,
            "prepare_progress_label": "Generuji Excel průvodky…",
        }
        mock_build.return_value = ([], [], [])
        url = reverse("waste_docs:yard_print_created") + f"?pks={self.ride.pk}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        mock_build.assert_not_called()
        self.assertContains(response, "data-print-prepare-form")
        content = response.content.decode()
        self.assertIn("client_bulk_print.js", content)
        self.assertIn("yard-merged-print-btn", content)
        self.assertIn(reverse("waste_docs:bulk_merged_print_pdf"), content)
        self.assertIn("autoPrint=true", content.replace(" ", ""))
        self.assertIn(self.drive_date.isoformat(), content)
        self.assertIn(str(self.ride.pk), content)

    def test_yard_print_created_requires_pks(self):
        url = reverse("waste_docs:yard_print_created")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
