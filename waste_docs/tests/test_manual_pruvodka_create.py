"""Ruční založení jízdy na /waste-docs/new/ bez požadavku zákazníka."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class ManualPruvodkaCreateTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("manual_create_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2036, 7, 20)

        self.name = NameCatalog.objects.create(value="Ruční založení subjekt")
        self.ico = IcoCatalog.objects.create(value="11223344")
        self.subject = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Hlavní, 10, Mladá Boleslav")
        ap = self.subject.address_profile
        ap.fulfillment_address = self.address
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W manual create")
        self.suf = SuffixCatalog.objects.create(value="H")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Přistavit manual")
        self.activity.vehicle_kinds.add(self.vk)
        ActivityFieldRule.objects.filter(activity=self.activity).delete()
        for field_key in (
            ActivityFieldKey.CONTAINER_1,
            ActivityFieldKey.SND_CISLO,
            ActivityFieldKey.ZPO,
        ):
            ActivityFieldRule.objects.create(
                activity=self.activity,
                field_key=field_key,
                mode=ActivityFieldMode.OFF,
            )

        self.rz = VehicleRzCatalog.objects.create(value="1AB2345")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="MAN-D1", last_name="Novák")

    def test_get_create_page_ok(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:create") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Založit jízdu")
        self.assertContains(response, "novalidate")

    def test_post_manual_create_without_customer_request(self):
        client = Client()
        client.force_login(self.dispecer)
        before = Pruvodka.objects.count()
        data = {
            "activity": str(self.activity.pk),
            "drive_date": self.day.isoformat(),
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz.pk),
            "container_number": "",
            "container_number_2": "",
            "fulfillment_address_value": self.address.value,
            "repeat_count": "1",
        }
        response = client.post(reverse("waste_docs:create"), data)
        self.assertEqual(response.status_code, 302, msg=response.content.decode()[:2000])
        self.assertEqual(Pruvodka.objects.count(), before + 1)
        ride = Pruvodka.objects.order_by("-pk").first()
        self.assertIsNotNone(ride)
        self.assertEqual(ride.driver_id, self.driver.pk)
        self.assertEqual(ride.vehicle_rz_id, self.rz.pk)
        self.assertEqual(ride.drive_date, self.day)
