from __future__ import annotations

from datetime import date

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class DashboardBulkPrintPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("dash_bulk_print", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2026, 8, 1)
        self.ride = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="Subjekt dash bulk print"),
            ico=IcoCatalog.objects.create(value="99887766"),
            address=AddressCatalog.objects.create(value="Adr dash bulk"),
            waste_type=WasteTypeCatalog.objects.create(code="990088", value="Wdb"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDB"),
            waste_category=WasteCategoryCatalog.objects.create(value="KODB"),
            suffix=SuffixCatalog.objects.create(value="SFXDB"),
            drive_date=self.drive_date,
            vehicle_rz=VehicleRzCatalog.objects.create(value="3C33333"),
            container_number="",
            created_by=self.user,
        )

    def test_dashboard_bulk_print_page_has_modal_controls(self):
        url = reverse("waste_docs:dashboard_bulk_print")
        response = self.client.get(url, {"date": self.drive_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="bulk-print-open-modal"', content)
        self.assertIn('id="bulk-print-modal"', content)
        self.assertIn('id="bulk-print-config"', content)
        self.assertIn('"driver_id": ""', content)

    @patch("waste_docs.views.dashboard_bulk.print_prepare_context")
    @patch("waste_docs.views.dashboard_bulk.build_print_rows_and_files")
    def test_dashboard_bulk_print_omits_pio_rows(self, mock_build_rows, mock_prepare_ctx):
        mock_prepare_ctx.return_value = {"needs_print_prepare": False}
        mock_build_rows.return_value = ([], [{"kind": "xlsx", "label": "Průvodka"}], [])
        url = reverse("waste_docs:dashboard_bulk_print")
        response = self.client.get(url, {"date": self.drive_date.isoformat()})
        self.assertEqual(response.status_code, 200)
        mock_build_rows.assert_called_once()
        self.assertIs(mock_build_rows.call_args.kwargs.get("include_pio"), False)
        self.assertIs(mock_build_rows.call_args.kwargs.get("ensure_zpo"), True)
