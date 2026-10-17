"""Založení průvodky ze sběrného dvora — výběr řidiče (nova-jizda)."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverAbsence,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka, SvozYardDriverPlan


class YardRideCreateDriverTests(TestCase):
    def setUp(self):
        self.today = date(2036, 3, 10)
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_nova", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)

        self.name = NameCatalog.objects.create(value="Nova jizda yard")
        self.ico = IcoCatalog.objects.create(value="88887777")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="SD Nova",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_pruvodka = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        adr = AddressCatalog.objects.create(value="Ulice 1, Město")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200310", value="O nova")
        self.suf = SuffixCatalog.objects.create(value="KN")
        self.vk = VehicleKindCatalog.objects.create(name="Hák nova", shortcut="H")
        self.activity = ActivityCatalog.objects.create(name="Průvodka nova")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

        self.rz = VehicleRzCatalog.objects.create(value="1N11111")
        prof_rz = VehicleRzProfile.objects.create(rz=self.rz)
        prof_rz.vehicle_kinds.add(self.vk)

        self.driver_a = DriverProfile.objects.create(personal_number="NV-A", last_name="Alpha")
        self.driver_b = DriverProfile.objects.create(personal_number="NV-B", last_name="Beta")

        SvozYardDriverPlan.objects.create(
            plan_date=self.today,
            subject_profile=self.subject,
            driver=self.driver_a,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.today,
            subject_profile=self.subject,
            driver=self.driver_b,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=1,
        )

        self.container_number = "CNT-NOVA-1"
        ContainerPassport.objects.create(
            container_number=self.container_number,
            vehicle_kind=self.vk,
            color="—",
        )

        self.url = reverse("waste_docs:yard_ride_create")
        self.client = Client()
        self.client.force_login(self.yard_user)

    def _post(self, **extra):
        data = {
            "pair_pk": [str(self.pair.pk)],
            f"vehicle_rz_{self.pair.pk}": str(self.rz.pk),
            f"container_{self.pair.pk}": self.container_number,
            f"weight_{self.pair.pk}": "100,2",
        }
        data.update(extra)
        with patch.object(timezone, "localdate", return_value=self.today):
            return self.client.post(self.url, data)

    def test_get_includes_validate_url_and_script(self):
        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        self.assertContains(response, reverse("waste_docs:yard_ride_validate_container"))
        self.assertContains(response, "yard_ride_container_validate.js")

    def test_get_includes_driver_select_and_container_label(self):
        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        content = response.content.decode()
        self.assertIn("yard-driver-select", content)
        self.assertIn('for="container_', content)
        self.assertIn('name="weight_', content)
        self.assertIn("Hmotnost (t)", content)
        self.assertNotIn('name="note_', content)
        self.assertNotIn(">Poznámka<", content)

    def test_get_includes_rz_options_and_json_script(self):
        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="yard-ride-rz-drivers"', content)
        self.assertIn("rzDriversData", content)
        self.assertIn("Alpha", content)
        self.assertIn(self.rz.value, content)
        self.assertIn(f'value="{self.rz.pk}"', content)

    def test_rz_from_plan_when_vehicle_profile_missing(self):
        VehicleRzProfile.objects.filter(rz=self.rz).delete()
        from waste_docs.services.yard_ride_rz_options import rz_options_for_yard_row

        opts = rz_options_for_yard_row(self.pair, self.subject, self.today)
        self.assertEqual(len(opts), 1)
        self.assertEqual(opts[0]["pk"], self.rz.pk)

        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        self.assertContains(response, self.rz.value)

    def test_post_without_driver_rejected(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vyberte řidiče")
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_post_with_invalid_driver_rejected(self):
        other = DriverProfile.objects.create(personal_number="NV-X", last_name="Cizí")
        response = self._post(**{f"driver_{self.pair.pk}": str(other.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "není pro vozidlo")
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_post_with_unknown_container_rejected(self):
        response = self._post(
            **{
                f"container_{self.pair.pk}": "999-unknown",
                f"driver_{self.pair.pk}": str(self.driver_b.pk),
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "není v číselníku pasportů")
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_post_with_valid_driver_creates_pruvodka(self):
        response = self._post(**{f"driver_{self.pair.pk}": str(self.driver_b.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pruvodka.objects.count(), 1)
        ride = Pruvodka.objects.get()
        self.assertEqual(ride.driver_id, self.driver_b.pk)
        self.assertEqual(ride.vehicle_rz_id, self.rz.pk)
        self.assertEqual(ride.weight_t, Decimal("100.2"))
        self.assertEqual(ride.weight_snapshot, "100,2")

    def test_post_uses_pair_fulfillment_address_over_central(self):
        pair_addr = AddressCatalog.objects.create(value="Adresa z páru, 5, Město")
        self.pair.fulfillment_address = pair_addr
        self.pair.save(update_fields=["fulfillment_address_id"])
        response = self._post(**{f"driver_{self.pair.pk}": str(self.driver_b.pk)})
        self.assertEqual(response.status_code, 302)
        ride = Pruvodka.objects.get()
        self.assertEqual(ride.address_id, pair_addr.pk)
        self.assertEqual(ride.address_snapshot, pair_addr.value)

    def test_post_without_weight_rejected(self):
        response = self._post(
            **{
                f"driver_{self.pair.pk}": str(self.driver_b.pk),
                f"weight_{self.pair.pk}": "",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zadejte hmotnost")
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_post_with_zero_weight_rejected(self):
        response = self._post(
            **{
                f"driver_{self.pair.pk}": str(self.driver_b.pk),
                f"weight_{self.pair.pk}": "0",
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "větší než 0")
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_post_with_dot_decimal_weight(self):
        response = self._post(
            **{
                f"driver_{self.pair.pk}": str(self.driver_b.pk),
                f"weight_{self.pair.pk}": "100.5",
            }
        )
        self.assertEqual(response.status_code, 302)
        ride = Pruvodka.objects.get()
        self.assertEqual(ride.weight_t, Decimal("100.5"))
        self.assertEqual(ride.weight_snapshot, "100,5")

    def test_single_driver_on_rz_auto_fill_data(self):
        SvozYardDriverPlan.objects.filter(driver=self.driver_b).delete()
        from waste_docs.services.yard_ride_plan_drivers import drivers_by_rz_for_yard_day

        drivers = drivers_by_rz_for_yard_day(self.subject, self.today).get(self.rz.pk, [])
        self.assertEqual(len(drivers), 1)
        self.assertEqual(drivers[0]["id"], self.driver_a.pk)

        response = self._post(**{f"driver_{self.pair.pk}": str(self.driver_a.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pruvodka.objects.get().driver_id, self.driver_a.pk)

    def _create_today_ride(self, driver: DriverProfile) -> Pruvodka:
        return Pruvodka.objects.create(
            activity=self.activity,
            drive_date=self.today,
            driver=driver,
            vehicle_rz=self.rz,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC-YRD"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC-YRD"),
            suffix=self.suf,
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr YRD"),
            container_number="OTHER-CNT",
            vehicle_rz_snapshot=self.rz.value,
            driver_snapshot=driver.last_name or "",
            created_by=self.yard_user,
            source_waste_suffix_pair=self.pair,
        )

    def test_driver_from_today_ride_without_plan_slot(self):
        SvozYardDriverPlan.objects.all().delete()
        ride_driver = DriverProfile.objects.create(personal_number="NV-R", last_name="RideOnly")
        self._create_today_ride(ride_driver)

        from waste_docs.services.yard_ride_plan_drivers import drivers_by_rz_for_yard_day

        drivers = drivers_by_rz_for_yard_day(self.subject, self.today).get(self.rz.pk, [])
        self.assertEqual(len(drivers), 1)
        self.assertEqual(drivers[0]["id"], ride_driver.pk)

        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        self.assertContains(response, "RideOnly")

        response = self._post(**{f"driver_{self.pair.pk}": str(ride_driver.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pruvodka.objects.count(), 2)

    def test_plan_and_ride_same_driver_deduplicated(self):
        SvozYardDriverPlan.objects.all().delete()
        SvozYardDriverPlan.objects.create(
            plan_date=self.today,
            subject_profile=self.subject,
            driver=self.driver_a,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        self._create_today_ride(self.driver_a)

        from waste_docs.services.yard_ride_plan_drivers import drivers_by_rz_for_yard_day

        drivers = drivers_by_rz_for_yard_day(self.subject, self.today).get(self.rz.pk, [])
        self.assertEqual(len(drivers), 1)
        self.assertEqual(drivers[0]["id"], self.driver_a.pk)

    def test_absent_driver_from_ride_not_offered(self):
        SvozYardDriverPlan.objects.all().delete()
        absent_driver = DriverProfile.objects.create(personal_number="NV-AB", last_name="Absent")
        self._create_today_ride(absent_driver)
        DriverAbsence.objects.create(
            driver=absent_driver,
            absence_type=DriverAbsence.AbsenceType.VACATION,
            date_from=self.today,
            date_to=self.today,
            is_partial=False,
        )

        from waste_docs.services.yard_ride_plan_drivers import drivers_by_rz_for_yard_day

        drivers = drivers_by_rz_for_yard_day(self.subject, self.today).get(self.rz.pk, [])
        self.assertEqual(drivers, [])

        response = self._post(**{f"driver_{self.pair.pk}": str(absent_driver.pk)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "není pro vozidlo")
        self.assertEqual(Pruvodka.objects.count(), 1)
