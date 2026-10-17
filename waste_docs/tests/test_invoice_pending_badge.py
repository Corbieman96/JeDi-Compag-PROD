"""Badge Zálohy a fronta schvalování — jen neschválené zálohové požadavky."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
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
from core.services.dashboard_customer_requests import build_customer_request_counts
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ADMIN, ROLE_KONTROLOR
from users.services.roles import set_user_role


class InvoicePendingBadgeTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("zalohy_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.kontrolor = User.objects.create_user("zalohy_kontr", password="pw")
        set_user_role(self.kontrolor, ROLE_KONTROLOR)
        self.day = date(2039, 3, 10)

        self.name = NameCatalog.objects.create(value="Subjekt zálohy badge")
        self.ico = IcoCatalog.objects.create(value="11223344")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Záloha ulice, 1, Město")
        self.wt = WasteTypeCatalog.objects.create(code="170101", value="W záloha")
        self.suf = SuffixCatalog.objects.create(value="ZL")
        self.vk = VehicleKindCatalog.objects.create(name="Hák záloha", shortcut="Hz", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz záloha", visible_for_submitter=True)

    def _cr(self, **kwargs):
        defaults = dict(
            created_by=self.admin,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.SUBMITTED,
            requires_advance_invoice=True,
            advance_invoice_amount=Decimal("1000.00"),
            invoice_due_date=self.day,
        )
        defaults.update(kwargs)
        return CustomerRequest.objects.create(**defaults)

    def test_badge_ignores_submitted_without_advance_invoice(self):
        self._cr(requires_advance_invoice=False, advance_invoice_amount=None, invoice_due_date=None)
        req = RequestFactory().get("/")
        req.user = self.admin
        counts = build_customer_request_counts(req, ROLE_ADMIN)
        self.assertEqual(counts["invoice_pending"], 0)

    def test_badge_counts_advance_submitted_and_clears_after_approve(self):
        item = self._cr()
        req = RequestFactory().get("/")
        req.user = self.kontrolor
        counts = build_customer_request_counts(req, ROLE_KONTROLOR)
        self.assertEqual(counts["invoice_pending"], 1)

        item.mark_invoice_approved(self.kontrolor, "Schváleno")
        item.save()
        counts_after = build_customer_request_counts(req, ROLE_KONTROLOR)
        self.assertEqual(counts_after["invoice_pending"], 0)
        self.assertEqual(item.status, CustomerRequest.Status.DISPATCHER_REVIEW)

    def test_invoice_queue_shows_submitted_with_null_due_date(self):
        item = self._cr(invoice_due_date=None)
        client = Client()
        client.force_login(self.kontrolor)
        response = client.get(reverse("waste_docs:customer_request_invoice_queue"))
        self.assertEqual(response.status_code, 200)
        overdue_pks = {r.pk for r in response.context["rows_overdue"]}
        self.assertIn(item.pk, overdue_pks)
        self.assertEqual(response.context["count_total"], 1)
