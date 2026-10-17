from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    DriverProfile,
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
from waste_docs.services.ride_protocol_xlsx import rides_for_protocol_group


class RideProtocolPdfEndpointTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("protocol_pdf_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2026, 7, 2)
        self.rz = VehicleRzCatalog.objects.create(value="2B22222")
        self.driver_a = DriverProfile.objects.create(
            first_name="Jan",
            last_name="Hlaváček",
            personal_number="2001",
        )
        self.driver_b = DriverProfile.objects.create(
            first_name="Petr",
            last_name="Novák",
            personal_number="2002",
        )
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt protocol pdf"),
            ico=IcoCatalog.objects.create(value="87654321"),
            address=AddressCatalog.objects.create(value="Adr protocol pdf"),
            waste_type=WasteTypeCatalog.objects.create(code="990098", value="Wpp"),
            waste_code=WasteCodeCatalog.objects.create(value="WCPP"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOPP"),
            suffix=SuffixCatalog.objects.create(value="SFXPP"),
            drive_date=self.drive_date,
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="2B22222",
            created_by=self.user,
            container_number="",
        )
        self.ride_a = Pruvodka.objects.create(
            driver=self.driver_a,
            driver_snapshot="Hlaváček Jan",
            ride_group_number=20,
            ride_sequence=1,
            created_at=datetime(2026, 7, 2, 8, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_b = Pruvodka.objects.create(
            driver=self.driver_b,
            driver_snapshot="Novák Petr",
            ride_group_number=20,
            ride_sequence=1,
            created_at=datetime(2026, 7, 2, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )

    def test_protocol_group_filters_by_driver(self):
        rides_a = rides_for_protocol_group(
            self.drive_date,
            self.rz.pk,
            self.user,
            driver_id=self.driver_a.pk,
        )
        self.assertEqual([r.pk for r in rides_a], [self.ride_a.pk])

    @patch("waste_docs.views.ride_protocol._ensure_protocol_pdf")
    @patch("waste_docs.views.ride_protocol.generate_protocol_xlsx")
    def test_ride_protocol_group_pdf_returns_pdf(self, mock_generate, mock_pdf):
        pdf_path = Path(__file__).with_name("_tmp_protocol_out.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 test")
        mock_generate.return_value = Path("dummy.xlsx")
        mock_pdf.return_value = pdf_path
        url = reverse("waste_docs:ride_protocol_group_pdf")
        response = self.client.get(
            url,
            {
                "date": self.drive_date.isoformat(),
                "vehicle_rz_id": self.rz.pk,
                "driver_id": self.driver_a.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        body = b"".join(response.streaming_content)
        self.assertTrue(body.startswith(b"%PDF"))
        mock_generate.assert_called_once()
        called_rides = mock_generate.call_args[0][0]
        self.assertEqual([r.pk for r in called_rides], [self.ride_a.pk])
        response.close()

    @patch("waste_docs.views.ride_protocol._ensure_protocol_pdf")
    @patch("waste_docs.views.ride_protocol.generate_protocol_xlsx")
    def test_ride_protocol_single_pdf_returns_pdf(self, mock_generate, mock_pdf):
        pdf_path = Path(__file__).with_name("_tmp_single_protocol.pdf")
        pdf_path.write_bytes(b"%PDF-1.4 single")
        mock_generate.return_value = Path("dummy.xlsx")
        mock_pdf.return_value = pdf_path
        url = reverse("waste_docs:ride_protocol_single_pdf", kwargs={"pk": self.ride_a.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        response.close()
