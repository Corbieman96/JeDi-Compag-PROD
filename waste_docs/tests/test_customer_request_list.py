from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from customer_requests.models import CustomerRequest, CustomerRequestAuditLog
from users.constants import ROLE_ADMIN, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.services.customer_request_status.align_ride_date import RIDE_RESCHEDULED_AUDIT_ACTION


class CustomerRequestListPaginationTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("cr_list_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.zadavatel = User.objects.create_user("cr_list_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.other = User.objects.create_user("cr_list_other", password="pw")
        set_user_role(self.other, ROLE_ZADAVATEL)

        self.activity = ActivityCatalog.objects.create(name="Svoz list", visible_for_submitter=True)
        self.address = AddressCatalog.objects.create(value="List ulice 1")
        self.wt = WasteTypeCatalog.objects.create(code="190101", value="List odpad")
        self.suf = SuffixCatalog.objects.create(value="List koncovka")
        self.vk = VehicleKindCatalog.objects.create(name="Hák list", shortcut="Hl", sort_order=0)

        self.names = []
        for i in range(55):
            name = NameCatalog.objects.create(value=f"Subjekt list {i:02d}")
            NameSubjectProfile.objects.create(name=name, ico=IcoCatalog.objects.create(value=f"88{i:04d}"))
            self.names.append(name)
            CustomerRequest.objects.create(
                created_by=self.zadavatel if i % 2 == 0 else self.other,
                name=name,
                activity=self.activity,
                vehicle_kind=self.vk,
                waste_type=self.wt,
                suffix=self.suf,
                address=self.address,
                target_date=date(2038, 7, 1) + timedelta(days=i),
                contract_number=f"SML-{i:03d}",
                status=CustomerRequest.Status.DISPATCHER_REVIEW,
            )

        self.special = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=NameCatalog.objects.create(value="Unikátní hledací subjekt XYZ"),
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2038, 8, 1),
            contract_number="SML-UNIQUE-999",
            status=CustomerRequest.Status.PLANNED,
        )
        NameSubjectProfile.objects.create(
            name=self.special.name,
            ico=IcoCatalog.objects.create(value="88777777"),
        )

        self.client = Client()
        self.url = reverse("waste_docs:customer_request_list")

    def test_list_paginates_at_default_per_page(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Řádků na stránku")
        self.assertContains(resp, "Další")
        self.assertEqual(len(resp.context["items"]), 50)

    def test_second_page_returns_remaining_rows(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url, {"page": 2, "per_page": 25})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["items"]), 25)
        self.assertContains(resp, "Předchozí")

    def test_search_filters_by_subject_name(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url, {"q": "Unikátní hledací"})
        self.assertEqual(resp.status_code, 200)
        pks = [item.pk for item in resp.context["items"]]
        self.assertEqual(pks, [self.special.pk])

    def test_search_filters_by_contract_number(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self.url, {"q": "SML-UNIQUE-999"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["items"][0].pk, self.special.pk)

    def test_status_filter_preserved_in_pagination_links(self):
        self.client.force_login(self.admin)
        CustomerRequest.objects.filter(pk=self.special.pk).update(status=CustomerRequest.Status.PLANNED)
        for i in range(30):
            CustomerRequest.objects.create(
                created_by=self.zadavatel,
                name=self.names[0],
                activity=self.activity,
                vehicle_kind=self.vk,
                waste_type=self.wt,
                suffix=self.suf,
                address=self.address,
                target_date=date(2038, 9, 1) + timedelta(days=i),
                status=CustomerRequest.Status.PLANNED,
            )
        resp = self.client.get(self.url, {"status": "planned", "per_page": 25})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "status=planned")
        self.assertContains(resp, "Další")

    def test_zadavatel_sees_only_own_requests(self):
        self.client.force_login(self.zadavatel)
        resp = self.client.get(self.url, {"per_page": 200})
        self.assertEqual(resp.status_code, 200)
        for item in resp.context["items"]:
            self.assertEqual(item.created_by_id, self.zadavatel.pk)

    def test_fixable_requests_sorted_before_others(self):
        fix_cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=NameCatalog.objects.create(value="Subjekt k opravě"),
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2038, 10, 1),
            status=CustomerRequest.Status.RETURNED_FOR_FIX,
        )
        newer_planned = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=NameCatalog.objects.create(value="Subjekt novější naplánovaný"),
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2038, 10, 2),
            status=CustomerRequest.Status.PLANNED,
        )
        self.assertGreater(newer_planned.created_at, fix_cr.created_at)

        self.client.force_login(self.zadavatel)
        resp = self.client.get(self.url, {"per_page": 200})
        self.assertEqual(resp.status_code, 200)
        pks = [item.pk for item in resp.context["items"]]
        self.assertIn(fix_cr.pk, pks)
        self.assertIn(newer_planned.pk, pks)
        self.assertLess(pks.index(fix_cr.pk), pks.index(newer_planned.pk))

    def test_reschedule_badge_only_when_audit_exists(self):
        self.client.force_login(self.admin)
        params = {"q": "Unikátní hledací"}
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([item.pk for item in resp.context["items"]], [self.special.pk])
        self.assertNotContains(resp, "Přeplánováno")

        CustomerRequestAuditLog.objects.create(
            request=self.special,
            actor=self.admin,
            action=RIDE_RESCHEDULED_AUDIT_ACTION,
            note="Jízda #4335 přeplánována na 19.09.2026",
        )
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Přeplánováno")
        self.assertContains(resp, "Požadavek byl přeplánován dispečerem")
        self.assertContains(resp, "#4335")
        row = next(r for r in resp.context["page_rows"] if r["item"].pk == self.special.pk)
        self.assertIn("Jízda #4335", row["reschedule_info"])
