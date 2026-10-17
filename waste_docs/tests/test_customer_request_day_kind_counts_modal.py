"""Modal počtů jízd, požadavků a řidičů za den na detailu požadavku."""

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
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_day_kind_counts_modal import (
    build_day_kind_counts_modal_payload,
    customer_request_counts_by_vehicle_kind_bucket,
    driver_counts_on_rides_by_vehicle_kind_bucket,
)
from waste_docs.services.pruvodka_day_kind_counts import ride_counts_by_vehicle_kind_bucket


class CustomerRequestDayKindCountsModalServiceTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_modal_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2026, 8, 4)

        self.vk_h = VehicleKindCatalog.objects.create(name="Hák modal", shortcut="H", sort_order=0)
        self.vk_a = VehicleKindCatalog.objects.create(name="Atego modal", shortcut="A", sort_order=1)
        clear_vehicle_kind_compatibility_cache()

        self.name = NameCatalog.objects.create(value="Subjekt modal")
        self.ico = IcoCatalog.objects.create(value="44556677")
        self.activity = ActivityCatalog.objects.create(name="Činnost modal")
        self.wt = WasteTypeCatalog.objects.create(code="200388", value="W modal")
        self.suf = SuffixCatalog.objects.create(value="S modal")
        self.address = AddressCatalog.objects.create(value="Ulice, 1, Město")

        self.driver_1 = DriverProfile.objects.create(personal_number="CRD1", last_name="Řidič 1")
        self.driver_2 = DriverProfile.objects.create(personal_number="CRD2", last_name="Řidič 2")

        self.rz_h = VehicleRzCatalog.objects.create(value="RZ-H-MODAL")
        prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        prof_h.vehicle_kinds.add(self.vk_h)

        ride_base = {
            "name": self.name,
            "ico": self.ico,
            "address": self.address,
            "waste_type": self.wt,
            "waste_code": WasteCodeCatalog.objects.create(value="20 03 88"),
            "waste_category": WasteCategoryCatalog.objects.create(value="K modal"),
            "suffix": self.suf,
            "drive_date": self.day,
            "created_by": self.dispecer,
            "container_number": "",
        }
        Pruvodka.objects.create(**ride_base, vehicle_rz=self.rz_h, driver=self.driver_1)
        Pruvodka.objects.create(**ride_base, vehicle_rz=self.rz_h, driver=self.driver_1)
        Pruvodka.objects.create(**ride_base, vehicle_rz=self.rz_h, driver=self.driver_2)

        self.cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk_a,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        )
        CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            vehicle_kind=None,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
        )

    def test_ride_counts_unchanged_after_bucket_extract(self):
        summary = ride_counts_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(summary.total, 3)
        self.assertEqual(next(row.count for row in summary.rows if row.key == "hak"), 3)

    def test_driver_counts_distinct_per_bucket(self):
        summary = driver_counts_on_rides_by_vehicle_kind_bucket(self.dispecer, self.day)
        self.assertEqual(summary.total, 2)
        self.assertEqual(next(row.count for row in summary.rows if row.key == "hak"), 2)

    def test_customer_request_counts_by_vehicle_kind_bucket(self):
        summary = customer_request_counts_by_vehicle_kind_bucket(self.day)
        self.assertEqual(summary.total, 2)
        self.assertEqual(next(row.count for row in summary.rows if row.key == "atego"), 1)
        self.assertEqual(summary.unclassified, 1)

    def test_build_modal_payload_has_three_sections(self):
        payload = build_day_kind_counts_modal_payload(self.dispecer, self.day)
        self.assertEqual(payload["date"], self.day.isoformat())
        self.assertEqual(len(payload["sections"]), 3)
        rides, requests, drivers = payload["sections"]
        self.assertEqual(rides["key"], "rides")
        self.assertEqual(rides["total"], 3)
        self.assertEqual(requests["key"], "requests")
        self.assertEqual(requests["total"], 2)
        self.assertEqual(drivers["key"], "drivers")
        self.assertEqual(drivers["total"], 2)
        self.assertEqual(drivers["counts"][2], 2)


class CustomerRequestDayKindCountsModalViewTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_modal_view_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_modal_view_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2026, 8, 5)
        self.other_day = date(2026, 9, 1)

        self.name = NameCatalog.objects.create(value="Subjekt view modal")
        self.activity = ActivityCatalog.objects.create(name="Činnost view")
        self.wt = WasteTypeCatalog.objects.create(code="200389", value="W view")
        self.suf = SuffixCatalog.objects.create(value="S view")
        self.address = AddressCatalog.objects.create(value="Adr view")

        self.cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
        )
        self.url = reverse("waste_docs:customer_request_day_kind_counts", kwargs={"pk": self.cr.pk})

    def test_api_forbidden_for_submitter(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_api_returns_target_date_for_dispatcher(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["date"], self.day.isoformat())
        self.assertEqual(len(payload["data"]["sections"]), 3)

    def test_list_does_not_show_button(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(reverse("waste_docs:customer_request_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="cr-day-kind-counts-open"')

    def test_detail_shows_button_for_dispatcher(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(reverse("waste_docs:customer_request_detail", kwargs={"pk": self.cr.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="cr-day-kind-counts-open"')
        self.assertContains(response, "Počet jízd")
