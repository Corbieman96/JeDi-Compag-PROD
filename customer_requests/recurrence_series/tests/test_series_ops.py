from __future__ import annotations

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    SuffixCatalog,
    WasteTypeCatalog,
)
from customer_requests.models import CustomerRequest
from customer_requests.recurrence_series.services.cancel import (
    cancel_open_occurrences,
    cancel_series_range,
)
from customer_requests.recurrence_series.services.series_ops import (
    is_open_occurrence,
    propagate_fields,
    series_occurrences,
)
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role


class RecurrenceSeriesModuleTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.disp = User.objects.create_user("series_disp", password="pw")
        set_user_role(self.disp, ROLE_DISPECER)
        self.zad = User.objects.create_user("series_zad", password="pw")
        set_user_role(self.zad, ROLE_ZADAVATEL)

        self.name = NameCatalog.objects.create(value="Serie Test a.s.")
        self.addr = AddressCatalog.objects.create(value="Test 1")
        self.wt = WasteTypeCatalog.objects.create(value="Odpad S")
        self.suf = SuffixCatalog.objects.create(value="*")
        self.act = ActivityCatalog.objects.create(name="Svoz")

        self.start = date(2031, 1, 5)  # Monday
        self.root = CustomerRequest.objects.create(
            created_by=self.zad,
            name=self.name,
            activity=self.act,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.addr,
            target_date=self.start,
            is_recurring=True,
            recurrence_weekdays="0",
            recurrence_until=self.start + timedelta(days=21),
            status=CustomerRequest.Status.DONE,
            dispatcher_review_by=self.disp,
        )
        self.child_open = CustomerRequest.objects.create(
            created_by=self.zad,
            name=self.name,
            activity=self.act,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.addr,
            target_date=self.start + timedelta(days=7),
            is_recurring=False,
            recurrence_parent_request=self.root,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
            note="old",
            dispatcher_review_by=self.disp,
        )
        self.child_open2 = CustomerRequest.objects.create(
            created_by=self.zad,
            name=self.name,
            activity=self.act,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.addr,
            target_date=self.start + timedelta(days=14),
            is_recurring=False,
            recurrence_parent_request=self.root,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
            dispatcher_review_by=self.disp,
        )

    def test_series_occurrences_ordered(self):
        rows = series_occurrences(self.child_open)
        self.assertEqual(
            [r.pk for r in rows],
            [self.root.pk, self.child_open.pk, self.child_open2.pk],
        )

    def test_cancel_selected_only(self):
        cancelled = cancel_open_occurrences(
            self.root,
            self.disp,
            reason="Test výběr",
            occurrence_ids=[self.child_open.pk],
        )
        self.assertEqual(len(cancelled), 1)
        self.child_open.refresh_from_db()
        self.child_open2.refresh_from_db()
        self.assertEqual(self.child_open.status, CustomerRequest.Status.CANCELLED)
        self.assertEqual(
            self.child_open2.status, CustomerRequest.Status.VISIBLE_FOR_DISPATCH
        )
        self.root.refresh_from_db()
        self.assertEqual(self.root.status, CustomerRequest.Status.DONE)

    def test_cancel_range(self):
        cancelled = cancel_series_range(
            self.root,
            self.disp,
            from_date=self.start + timedelta(days=10),
            to_date=self.start + timedelta(days=20),
            reason="Rozsah",
        )
        self.assertEqual(len(cancelled), 1)
        self.child_open.refresh_from_db()
        self.child_open2.refresh_from_db()
        self.assertEqual(
            self.child_open.status, CustomerRequest.Status.VISIBLE_FOR_DISPATCH
        )
        self.assertEqual(self.child_open2.status, CustomerRequest.Status.CANCELLED)

    def test_propagate_open(self):
        self.root.note = "from-root"
        self.root.save(update_fields=["note", "updated_at"])
        n = propagate_fields(self.root, self.disp)
        self.assertEqual(n, 2)
        self.child_open.refresh_from_db()
        self.assertEqual(self.child_open.note, "from-root")

    def test_manage_forbidden_for_zadavatel(self):
        client = Client()
        client.force_login(self.zad)
        url = reverse("customer_request_recurrence_series:manage", args=[self.root.pk])
        resp = client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_manage_ok_for_dispatcher_from_child(self):
        client = Client()
        client.force_login(self.disp)
        url = reverse(
            "customer_request_recurrence_series:manage", args=[self.child_open.pk]
        )
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, f"#{self.child_open.pk}")
        self.assertTrue(is_open_occurrence(self.child_open))
