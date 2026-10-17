from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.core.files.base import ContentFile
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
from users.constants import ROLE_DISPECER, ROLE_RIDIC
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class PruvodkaDetailDashboardLinkTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("detail_dash_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.ridic = User.objects.create_user("detail_dash_rid", password="pw")
        set_user_role(self.ridic, ROLE_RIDIC)
        self.ride_date = date(2027, 3, 15)
        name = NameCatalog.objects.create(value="Subjekt detail dash")
        self.ride = Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="11223344"),
            address=AddressCatalog.objects.create(value="Adr detail dash"),
            waste_type=WasteTypeCatalog.objects.create(code="990097", value="Wdd"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDD"),
            waste_category=WasteCategoryCatalog.objects.create(value="KODD"),
            suffix=SuffixCatalog.objects.create(value="SFXDD"),
            drive_date=self.ride_date,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P77777"),
            container_number="",
            created_by=self.dispecer,
        )

    def _dashboard_href(self) -> str:
        return f'{reverse("core:dashboard")}?date={self.ride_date.isoformat()}">Dashboard'

    def test_dispecer_sees_dashboard_link_with_ride_date(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "15.03.2027")
        evidence_html = response.content.decode().split("Evidence jízdy", 1)[1]
        self.assertLess(evidence_html.index("Datum jízdy"), evidence_html.index("Název F/P osoby"))
        self.assertContains(response, self._dashboard_href())

    def test_ridic_does_not_see_dashboard_link(self):
        self.ride.created_by = self.ridic
        self.ride.save(update_fields=("created_by",))
        client = Client()
        client.force_login(self.ridic)
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self._dashboard_href())

    def test_detail_shows_print_link_when_generated_file_exists(self):
        self.ride.generated_file.save(
            "detail_print_test.xlsx",
            ContentFile(b"PK"),
            save=True,
        )
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tisk (PDF)")
        self.assertContains(response, reverse("waste_docs:ride_pruvodka_pdf", kwargs={"pk": self.ride.pk}))

    @patch("waste_docs.views.pruvodka_pages.detail.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.views.pruvodka_pages.detail.system_may_generate_zpo_instance", return_value=True)
    def test_detail_ensures_zpo_instance_when_editable(self, _mock_may, mock_ensure):
        self.ride.activity = ActivityCatalog.objects.create(name="Svoz ZPO detail")
        self.ride.snd_cislo_listu = "0000491-2026-6"
        self.ride.save()
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        mock_ensure.assert_called_once_with(self.ride.pk)

    @patch("waste_docs.views.pruvodka_pages.detail.can_create_pruvodka", return_value=False)
    @patch("waste_docs.views.pruvodka_pages.detail.can_edit_existing_pruvodka", return_value=False)
    @patch("waste_docs.views.pruvodka_pages.detail.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.views.pruvodka_pages.detail.system_may_generate_zpo_instance", return_value=True)
    def test_detail_skips_ensure_zpo_when_read_only(self, _mock_may, mock_ensure, *_perms):
        self.ride.activity = ActivityCatalog.objects.create(name="Svoz ZPO detail RO")
        self.ride.snd_cislo_listu = "0000491-2026-6"
        self.ride.save()
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        mock_ensure.assert_not_called()
