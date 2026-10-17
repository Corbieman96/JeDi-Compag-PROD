"""Stažení schválení požadavku z dispatch fronty."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    SuffixCatalog,
    WasteTypeCatalog,
)
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.services.customer_request_dispatch import customer_requests_visible_for_dispatch
from waste_docs.services.customer_request_dispatcher_withdraw import (
    DispatcherWithdrawError,
    withdraw_from_dispatch,
)
from waste_docs.services.customer_request_status import sync_customer_request_status


class CustomerRequestDispatchWithdrawServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_withdraw_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_withdraw_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2037, 5, 13)

        self.cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=NameCatalog.objects.create(value="Withdraw subjekt"),
            activity=ActivityCatalog.objects.create(name="Withdraw svoz"),
            waste_type=WasteTypeCatalog.objects.create(code="200313", value="W wd"),
            suffix=SuffixCatalog.objects.create(value="KW"),
            address=AddressCatalog.objects.create(value="Withdraw adresa"),
            target_date=self.day,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
            dispatcher_review_by=self.dispecer,
            dispatcher_reviewed_at=timezone.now(),
        )

    def test_return_moves_to_returned_for_fix(self):
        withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="return", note="Omylem schváleno")
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.RETURNED_FOR_FIX)
        self.assertEqual(self.cr.dispatcher_note, "Omylem schváleno")

    def test_cancel_moves_to_cancelled(self):
        withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="cancel", note="Neplatný")
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.CANCELLED)

    def test_cancel_requires_reason(self):
        with self.assertRaises(DispatcherWithdrawError):
            withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="cancel", note="")
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.VISIBLE_FOR_DISPATCH)

    def test_removed_from_dispatch_panel(self):
        self.assertEqual(len(list(customer_requests_visible_for_dispatch(self.dispecer, self.day))), 1)
        withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="return")
        self.assertEqual(list(customer_requests_visible_for_dispatch(self.dispecer, self.day)), [])

    def test_sync_does_not_repromote_returned(self):
        withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="return")
        self.assertFalse(sync_customer_request_status(self.cr, actor=self.dispecer))
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.RETURNED_FOR_FIX)

    def test_blocks_when_ride_exists(self):
        from waste_docs.models import Pruvodka
        from catalogs.models import IcoCatalog, WasteCodeCatalog, WasteCategoryCatalog

        ride = Pruvodka.objects.create(
            name=self.cr.name,
            ico=IcoCatalog.objects.create(value="55443322"),
            address=self.cr.address,
            waste_type=self.cr.waste_type,
            waste_code=WasteCodeCatalog.objects.create(value="WCWD"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCWD"),
            suffix=self.cr.suffix,
            drive_date=self.day,
            created_by=self.dispecer,
            container_number="",
        )
        self.cr.planned_pruvodka = ride
        self.cr.status = CustomerRequest.Status.PLANNED
        self.cr.save(update_fields=["planned_pruvodka", "status"])

        with self.assertRaises(DispatcherWithdrawError):
            withdraw_from_dispatch(item=self.cr, actor=self.dispecer, action="return")


class CustomerRequestDispatchWithdrawViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_withdraw_view_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_withdraw_view_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2037, 5, 13)

        self.cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=NameCatalog.objects.create(value="Withdraw view subjekt"),
            activity=ActivityCatalog.objects.create(name="Withdraw view svoz"),
            waste_type=WasteTypeCatalog.objects.create(code="200314", value="W wdv"),
            suffix=SuffixCatalog.objects.create(value="KVW"),
            address=AddressCatalog.objects.create(value="Withdraw view adresa"),
            target_date=self.day,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
            dispatcher_review_by=self.dispecer,
            dispatcher_reviewed_at=timezone.now(),
        )

    def test_dispatcher_post_return(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_dispatch_withdraw", kwargs={"pk": self.cr.pk})
        response = client.post(url, {"action": "return", "note": "Opravte datum"})
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.RETURNED_FOR_FIX)

    def test_zadavatel_cannot_withdraw(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_dispatch_withdraw", kwargs={"pk": self.cr.pk})
        response = client.post(url, {"action": "return"})
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.VISIBLE_FOR_DISPATCH)

    def test_detail_shows_withdraw_form(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_detail", kwargs={"pk": self.cr.pk})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stažení schválení")
        self.assertContains(response, "Vrátit k opravě")
