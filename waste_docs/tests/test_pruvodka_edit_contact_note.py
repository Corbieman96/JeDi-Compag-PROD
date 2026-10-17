"""Úprava poznámky (contact_note) při editaci průvodky."""

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
    NameSubjectProfile,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from waste_docs.models import Pruvodka


@patch("waste_docs.views.pruvodka_edit.city_from_coords", return_value="Česko")
class PruvodkaEditContactNoteTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("note_edit", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt note edit")
        self.ico = IcoCatalog.objects.create(value="99112233")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico, contact_note="Z číselníku")

        self.address = AddressCatalog.objects.create(value="Ulice, 1, Město")
        self.ride = Pruvodka.objects.create(
            drive_date=date(2026, 6, 22),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=WasteTypeCatalog.objects.create(code="200302", value="W note"),
            waste_code=WasteCodeCatalog.objects.create(value="WCNE"),
            waste_category=WasteCategoryCatalog.objects.create(value="KONE"),
            suffix=SuffixCatalog.objects.create(value="Konc note"),
            vehicle_rz=VehicleRzCatalog.objects.create(value="1N11111"),
            contact_note="Původní poznámka",
            created_by=self.user,
        )
        self.edit_url = reverse("waste_docs:edit", kwargs={"pk": self.ride.pk})
        self.client = Client()
        self.client.force_login(self.user)

    def test_edit_contact_note_persists(self, _mock_city):
        response = self.client.post(
            self.edit_url,
            {
                "drive_date": self.ride.drive_date.strftime("%Y-%m-%d"),
                "name": str(self.ride.name_id),
                "ico": str(self.ride.ico_id),
                "waste_type": str(self.ride.waste_type_id),
                "suffix": str(self.ride.suffix_id),
                "vehicle_rz": str(self.ride.vehicle_rz_id),
                "fulfillment_address_value": self.address.value,
                "container_number": "",
                "container_number_2": "",
                "contact_phone": "",
                "contract_number": "",
                "contact_note": "Upravená poznámka",
                "repeat_count": "1",
            },
        )
        self.assertRedirects(
            response,
            reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}),
        )
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.contact_note, "Upravená poznámka")
