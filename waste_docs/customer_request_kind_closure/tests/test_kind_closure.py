"""Testy uzavření zákaznických požadavků podle druhu vozidla."""

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
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from core.models import AppSettings
from customer_requests.models import CustomerRequestVehicleKindClosure
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.customer_request_kind_closure.services.checks import (
    is_vehicle_kind_closed_for_day,
    vehicle_kind_closure_error,
)
from waste_docs.customer_request_kind_closure.services.toggle import toggle_vehicle_kind_closure
from waste_docs.forms.customer_request import CustomerRequestForm


class VehicleKindClosureHelperTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("vk_close_u", password="pw")
        self.day = date(2030, 5, 15)
        self.kind_a = VehicleKindCatalog.objects.create(
            name="Atego Close", shortcut="AClose", sort_order=1
        )
        self.kind_h = VehicleKindCatalog.objects.create(
            name="Hak Close", shortcut="HClose", sort_order=2
        )

    def test_toggle_closes_and_opens_kind(self):
        self.assertFalse(is_vehicle_kind_closed_for_day(self.day, self.kind_a.pk))
        closed = toggle_vehicle_kind_closure(self.user, self.day, self.kind_a.pk)
        self.assertTrue(closed)
        self.assertTrue(is_vehicle_kind_closed_for_day(self.day, self.kind_a.pk))
        self.assertFalse(is_vehicle_kind_closed_for_day(self.day, self.kind_h.pk))
        opened = toggle_vehicle_kind_closure(self.user, self.day, self.kind_a.pk)
        self.assertFalse(opened)
        self.assertFalse(is_vehicle_kind_closed_for_day(self.day, self.kind_a.pk))

    def test_error_only_for_closed_kind(self):
        toggle_vehicle_kind_closure(self.user, self.day, self.kind_a.pk)
        self.assertIsNotNone(
            vehicle_kind_closure_error(self.day, self.kind_a.pk, user=self.user)
        )
        self.assertIsNone(
            vehicle_kind_closure_error(self.day, self.kind_h.pk, user=self.user)
        )


class VehicleKindClosureFormTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("vk_close_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        settings = AppSettings.load()
        settings.customer_request_daily_cutoff_time = None
        settings.save(update_fields=["customer_request_daily_cutoff_time"])

        self.day = date(2030, 6, 20)
        self.name = NameCatalog.objects.create(value="VK Close Subjekt")
        self.ico = IcoCatalog.objects.create(value="55667788")
        self.subject = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Adr VK close")
        self.wt = WasteTypeCatalog.objects.create(code="200401", value="W VK close")
        self.suf = SuffixCatalog.objects.create(value="VKC")
        self.kind_a = VehicleKindCatalog.objects.create(
            name="Atego Form", shortcut="AF", sort_order=1
        )
        self.kind_h = VehicleKindCatalog.objects.create(
            name="Hak Form", shortcut="HF", sort_order=2
        )
        self.activity = ActivityCatalog.objects.create(
            name="Cinnost VK close", visible_for_submitter=True
        )
        self.activity.vehicle_kinds.add(self.kind_a, self.kind_h)
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_vehicle_kind=self.kind_a,
        )
        pair.yard_vehicle_kinds.add(self.kind_a, self.kind_h)
        CustomerRequestVehicleKindClosure.objects.create(
            closure_date=self.day,
            vehicle_kind=self.kind_a,
            is_closed=True,
            updated_by=self.zadavatel,
        )

    def _payload(self, *, vehicle_kind_id: int) -> dict:
        return {
            "name_existing": self.name.pk,
            "name_lookup": self.name.value,
            "activity": self.activity.pk,
            "vehicle_kind": vehicle_kind_id,
            "waste_type": self.wt.pk,
            "waste_type_lookup": self.wt.value,
            "suffix": self.suf.pk,
            "target_date": self.day.isoformat(),
            "address_value": self.address.value,
            "contact_phone": "",
            "contact_note": "",
            "note": "",
            "contract_number": "",
            "facility_address_value": "",
            "has_follow_up": False,
            "is_recurring": False,
            "requires_advance_invoice": False,
        }

    def test_form_blocks_closed_kind(self):
        form = CustomerRequestForm(data=self._payload(vehicle_kind_id=self.kind_a.pk))
        form.submit_user = self.zadavatel
        self.assertFalse(form.is_valid())
        self.assertIn("target_date", form.errors)

    def test_form_allows_other_kind(self):
        form = CustomerRequestForm(data=self._payload(vehicle_kind_id=self.kind_h.pk))
        form.submit_user = self.zadavatel
        self.assertTrue(form.is_valid(), form.errors)


class VehicleKindClosureToggleViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("vk_close_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.day = date(2030, 7, 1)
        self.kind = VehicleKindCatalog.objects.create(
            name="Atego View", shortcut="AV", sort_order=1
        )

    def test_dispatcher_can_toggle(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:customer_request_kind_closure_toggle")
        response = client.post(
            url,
            {"date": self.day.isoformat(), "vehicle_kind_id": str(self.kind.pk)},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(is_vehicle_kind_closed_for_day(self.day, self.kind.pk))
