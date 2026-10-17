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
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_KONTROLOR
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_dispatch import customer_requests_visible_for_dispatch
from waste_docs.services.customer_request_prefill import build_customer_request_prefill_bundle
from waste_docs.services.customer_request_vehicle_kind import effective_vehicle_kind_label


class CustomerRequestPruvodkaCreateTests(TestCase):
    databases = {"default", "addresses"}
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_create_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.kontrolor = User.objects.create_user("cr_create_kon", password="pw")
        set_user_role(self.kontrolor, ROLE_KONTROLOR)
        self.day = date(2036, 6, 15)

        self.name = NameCatalog.objects.create(value="Kofola test subjekt")
        self.ico = IcoCatalog.objects.create(value="87654321")
        self.subject = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Kaly, 1, Kaly")
        ap = self.subject.address_profile
        ap.fulfillment_address = self.address
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200399", value="W cr create")
        self.suf = SuffixCatalog.objects.create(value="H")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Přistavit")
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

        self.rz = VehicleRzCatalog.objects.create(value="8S74311")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="CR-D1", last_name="Vágner")

        self.cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        )

    def test_detail_shows_create_link_with_customer_request(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_detail", kwargs={"pk": self.cr.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Založit jízdu (vybrat řidiče a vozidlo)")
        self.assertContains(response, f"customer_request={self.cr.pk}")
        self.assertNotContains(response, "plan-rides")

    def test_panel_lists_customer_request_for_date(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:create") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"customer_request={self.cr.pk}")
        self.assertContains(response, "Požadavky — připravené pro dispečera")
        self.assertContains(response, "Kofola test subjekt")

    def test_get_prefills_from_customer_request(self):
        client = Client()
        client.force_login(self.dispecer)
        url = (
            reverse("waste_docs:create")
            + f"?date={self.day.isoformat()}&customer_request={self.cr.pk}"
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'name="customer_request" value="{self.cr.pk}"')
        self.assertContains(response, "Přistavit")
        self.assertContains(response, self.day.strftime("%Y-%m-%d"))

    def test_post_links_customer_request_to_pruvodka(self):
        client = Client()
        client.force_login(self.dispecer)
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
            "customer_request": str(self.cr.pk),
        }
        response = client.post(reverse("waste_docs:create"), data)
        self.assertEqual(response.status_code, 302)
        ride = Pruvodka.objects.order_by("-pk").first()
        self.assertIsNotNone(ride)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.planned_pruvodka_id, ride.pk)
        self.assertEqual(self.cr.status, CustomerRequest.Status.PLANNED)
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.dispecer, self.day)), [])

    def test_post_links_customer_request_when_drive_date_differs(self):
        other_day = self.day.replace(day=self.day.day + 1) if self.day.day < 28 else self.day.replace(day=self.day.day - 1)
        client = Client()
        client.force_login(self.dispecer)
        data = {
            "activity": str(self.activity.pk),
            "drive_date": other_day.isoformat(),
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
            "customer_request": str(self.cr.pk),
        }
        response = client.post(reverse("waste_docs:create"), data)
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.PLANNED)
        self.assertEqual(self.cr.target_date, other_day)
        self.assertIsNotNone(self.cr.planned_pruvodka_id)
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.dispecer, self.day)), [])
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.dispecer, other_day)), [])

    def test_post_ignores_already_planned_request(self):
        existing = Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="20 03 99"),
            waste_category=WasteCategoryCatalog.objects.create(value="O"),
            suffix=self.suf,
            drive_date=self.day,
            vehicle_rz=self.rz,
            created_by=self.dispecer,
        )
        self.cr.planned_pruvodka = existing
        self.cr.status = CustomerRequest.Status.PLANNED
        self.cr.save()

        client = Client()
        client.force_login(self.dispecer)
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
            "customer_request": str(self.cr.pk),
        }
        before_count = Pruvodka.objects.count()
        response = client.post(reverse("waste_docs:create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pruvodka.objects.count(), before_count + 1)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.planned_pruvodka_id, existing.pk)

    def test_dispatch_query_empty_for_kontrolor(self):
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.kontrolor, self.day)), [])

    def test_effective_vehicle_kind_from_activity_when_cr_fk_null(self):
        self.cr.vehicle_kind = None
        self.cr.save(update_fields=["vehicle_kind"])
        self.assertEqual(effective_vehicle_kind_label(self.cr), "Hák (H)")

    def test_panel_shows_effective_vehicle_kind_without_cr_fk(self):
        self.cr.vehicle_kind = None
        self.cr.save(update_fields=["vehicle_kind"])
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:create") + f"?date={self.day.isoformat()}"
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hák (H)")

    def test_detail_shows_effective_vehicle_kind_without_cr_fk(self):
        self.cr.vehicle_kind = None
        self.cr.save(update_fields=["vehicle_kind"])
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_detail", kwargs={"pk": self.cr.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Druh vozidla")
        self.assertContains(response, "Hák (H)")

    def test_prefill_sets_vehicle_kind_without_auto_driver_rz(self):
        self.cr.vehicle_kind = None
        self.cr.save(update_fields=["vehicle_kind"])
        self.driver.allowed_vehicle_kinds.add(self.vk)
        self.driver.allowed_vehicle_rz.add(self.prof)

        bundle = build_customer_request_prefill_bundle(self.cr)
        client = bundle["client"]
        self.assertEqual(client["required_vehicle_kind_id"], self.vk.pk)
        self.assertEqual(client["vehicle_kind_label"], "Hák (H)")
        self.assertIsNone(client["driver_id"])
        self.assertIsNone(client["vehicle_rz_id"])
        self.assertTrue(client["skip_driver_rz_auto_select"])
        self.assertNotIn("driver", bundle["initial"])
        self.assertNotIn("vehicle_rz", bundle["initial"])

    def test_prefill_uses_last_pair_own_address_not_cr_central(self):
        cr_addr = AddressCatalog.objects.create(value="Březno, 106, Březno")
        pair_addr = AddressCatalog.objects.create(value="Kosmonosy, 2, Kosmonosy")
        self.cr.address = cr_addr
        self.cr.save(update_fields=["address"])
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            sort_order=1,
        )
        pair_with_addr = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=pair_addr,
            yard_vehicle_kind=self.vk,
            sort_order=2,
        )
        pair_with_addr.yard_vehicle_kinds.add(self.vk)

        bundle = build_customer_request_prefill_bundle(self.cr)
        client = bundle["client"]
        self.assertEqual(client["fulfillment_address"], pair_addr.value)
        self.assertEqual(bundle["initial"]["fulfillment_address_value"], pair_addr.value)
        option_values = [row["value"] for row in client["fulfillment_address_options"]]
        self.assertEqual(option_values[0], pair_addr.value)
        self.assertIn(cr_addr.value, option_values)
        self.assertGreaterEqual(len(option_values), 2)

    def test_prefill_last_pair_own_address_without_vehicle_kind(self):
        pair_addr = AddressCatalog.objects.create(value="Kosmonosy, 2, Kosmonosy")
        self.cr.vehicle_kind = None
        self.cr.save(update_fields=["vehicle_kind"])
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            sort_order=1,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=pair_addr,
            sort_order=2,
        )

        bundle = build_customer_request_prefill_bundle(self.cr)
        client = bundle["client"]
        self.assertEqual(client["fulfillment_address"], pair_addr.value)
        self.assertEqual(bundle["initial"]["fulfillment_address_value"], pair_addr.value)

    def test_create_page_includes_pair_address_select(self):
        client = Client()
        client.force_login(self.dispecer)
        url = (
            reverse("waste_docs:create")
            + f"?date={self.day.isoformat()}&customer_request={self.cr.pk}"
        )
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pruvodka-pair-address-select")
        self.assertContains(response, "fulfillment_address_options")
