"""Úprava činnosti jízdy — adresa plnění a zpětná vazba při chybě."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    ActivityFieldKey,
    ActivityFieldMode,
    ActivityFieldRule,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from waste_docs.models import Pruvodka


@patch("waste_docs.views.pruvodka_edit.city_from_coords", return_value="Česko")
class PruvodkaEditActivityChangeTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("act_change", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt act change")
        self.ico = IcoCatalog.objects.create(value="88112233")
        self.facility_addr = AddressCatalog.objects.create(value="Vanurova, 1425, Mladá Boleslav")
        profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        profile.facility_address = self.facility_addr
        profile.save()

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W act")
        self.suf = SuffixCatalog.objects.create(value="Konc act")
        self.wc = WasteCodeCatalog.objects.create(value="20 03 01")
        self.wcat = WasteCategoryCatalog.objects.create(value="KO act")

        self.activity_no_addr = ActivityCatalog.objects.create(name="Jiná act test")
        self.activity_with_addr = ActivityCatalog.objects.create(name="Výměna act test")

        self.vk = VehicleKindCatalog.objects.create(name="Hák act", shortcut="Ha", sort_order=0)
        for act in (self.activity_no_addr, self.activity_with_addr):
            act.vehicle_kinds.add(self.vk)
            ActivityFieldRule.objects.filter(activity=act).delete()
            for key in (
                ActivityFieldKey.SUFFIX,
                ActivityFieldKey.WASTE_TYPE,
                ActivityFieldKey.NAME,
                ActivityFieldKey.VEHICLE_RZ,
                ActivityFieldKey.SND_CISLO,
            ):
                ActivityFieldRule.objects.create(
                    activity=act, field_key=key, mode=ActivityFieldMode.REQUIRED
                )
        ActivityFieldRule.objects.create(
            activity=self.activity_no_addr,
            field_key=ActivityFieldKey.FULFILLMENT_ADDRESS,
            mode=ActivityFieldMode.OFF,
        )
        ActivityFieldRule.objects.create(
            activity=self.activity_with_addr,
            field_key=ActivityFieldKey.FULFILLMENT_ADDRESS,
            mode=ActivityFieldMode.REQUIRED,
        )

        self.rz = VehicleRzCatalog.objects.create(value="9S06217")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="AC1", last_name="Hlaváček")

        self.ride = Pruvodka.objects.create(
            activity=self.activity_no_addr,
            drive_date=date(2026, 6, 22),
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value=""),
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            vehicle_rz=self.rz,
            driver=self.driver,
            created_by=self.user,
        )
        self.edit_url = reverse("waste_docs:edit", kwargs={"pk": self.ride.pk})
        self.client = Client()
        self.client.force_login(self.user)

    def _base_post(self, **overrides) -> dict[str, str]:
        data = {
            "activity": str(self.activity_with_addr.pk),
            "drive_date": self.ride.drive_date.strftime("%Y-%m-%d"),
            "repeat_count": "1",
            "name": str(self.ride.name_id),
            "ico": str(self.ride.ico_id),
            "waste_type": str(self.ride.waste_type_id),
            "suffix": str(self.ride.suffix_id),
            "vehicle_rz": str(self.ride.vehicle_rz_id),
            "driver": str(self.ride.driver_id),
            "container_number": "",
            "container_number_2": "",
            "contact_phone": "",
            "contract_number": "",
            "contact_note": "",
            "ico_lookup": self.name.value,
            "skip_follow_up": "",
            "follow_up_parent": "",
            "fulfillment_address_value": "",
        }
        data.update(overrides)
        return data

    def test_edit_activity_change_without_address_shows_errors(self, _mock_city):
        response = self.client.post(self.edit_url, self._base_post())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jízdu nelze uložit")
        self.assertContains(response, "Adresa plnění")
        self.assertContains(response, "pruvodka-form-error-summary")

        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("Jízdu se nepodařilo uložit" in m for m in msgs))
        self.assertTrue(any("Adresa plnění" in m for m in msgs))

        self.ride.refresh_from_db()
        self.assertEqual(self.ride.activity_id, self.activity_no_addr.pk)

    def test_edit_activity_change_with_facility_address_saves(self, _mock_city):
        response = self.client.post(
            self.edit_url,
            self._base_post(fulfillment_address_value=self.facility_addr.value),
        )
        self.assertRedirects(
            response,
            reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}),
        )
        self.ride.refresh_from_db()
        self.assertEqual(self.ride.activity_id, self.activity_with_addr.pk)
        self.assertEqual(self.ride.activity_snapshot, self.activity_with_addr.name)
