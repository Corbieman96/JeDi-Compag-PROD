from __future__ import annotations

from datetime import date

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
from catalogs.models.vehicle_rz import VehicleKindCatalog
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_for_pruvodka import (
    can_view_customer_request,
    source_customer_request_for_pruvodka,
)


class PruvodkaDetailCustomerRequestLinkTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("ride_cr_link_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.owner = User.objects.create_user("ride_cr_link_owner", password="pw")
        set_user_role(self.owner, ROLE_ZADAVATEL)
        self.other = User.objects.create_user("ride_cr_link_other", password="pw")
        set_user_role(self.other, ROLE_ZADAVATEL)
        self.day = date(2028, 6, 20)

        self.name = NameCatalog.objects.create(value="Subjekt ride CR link")
        self.ico = IcoCatalog.objects.create(value="55443322")
        self.address = AddressCatalog.objects.create(value="Link, 1, Město")
        self.wt = WasteTypeCatalog.objects.create(code="200501", value="W link")
        self.suf = SuffixCatalog.objects.create(value="L")
        self.vk = VehicleKindCatalog.objects.create(name="Hák link", shortcut="Hl", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Přistavit link", visible_for_submitter=True)

        self.ride = Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="20 05 01"),
            waste_category=WasteCategoryCatalog.objects.create(value="O"),
            suffix=self.suf,
            drive_date=self.day,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1L11111"),
            activity=self.activity,
            created_by=self.dispecer,
        )
        self.customer_request = CustomerRequest.objects.create(
            created_by=self.owner,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.PLANNED,
            planned_pruvodka=self.ride,
        )

    def test_ride_without_customer_request_has_no_link(self):
        wc, _ = WasteCodeCatalog.objects.get_or_create(value="20 05 02")
        wcat, _ = WasteCategoryCatalog.objects.get_or_create(value="O")
        standalone = Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=wc,
            waste_category=wcat,
            suffix=self.suf,
            drive_date=self.day,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1L22222"),
            created_by=self.dispecer,
        )
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(reverse("waste_docs:detail", kwargs={"pk": standalone.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Založeno z požadavku")

    def test_dispecer_sees_customer_request_link(self):
        client = Client()
        client.force_login(self.dispecer)
        response = client.get(reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Založeno z požadavku")
        self.assertContains(
            response,
            reverse("waste_docs:customer_request_detail", kwargs={"pk": self.customer_request.pk}),
        )

    def test_source_customer_request_resolves_planned_pruvodka(self):
        self.assertEqual(
            source_customer_request_for_pruvodka(self.ride),
            self.customer_request,
        )

    def test_can_view_customer_request_owner_and_other(self):
        self.assertTrue(can_view_customer_request(self.owner, self.customer_request))
        self.assertFalse(can_view_customer_request(self.other, self.customer_request))
        self.assertTrue(can_view_customer_request(self.dispecer, self.customer_request))
