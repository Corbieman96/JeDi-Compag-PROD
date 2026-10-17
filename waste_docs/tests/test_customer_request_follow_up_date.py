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
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm


class CustomerRequestFollowUpDateTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_fu_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_fu_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2037, 4, 10)
        self.follow_day = self.day + timedelta(days=3)

        self.name = NameCatalog.objects.create(value="Subjekt follow up date")
        self.ico = IcoCatalog.objects.create(value="11223355")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice, 5, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W fu")
        self.suf = SuffixCatalog.objects.create(value="H")
        self.vk = VehicleKindCatalog.objects.create(name="Hák fu", shortcut="Hf", sort_order=0)

        self.follow_activity = ActivityCatalog.objects.create(name="Odvézt fu", visible_for_submitter=True)
        self.activity = ActivityCatalog.objects.create(name="Přistavit fu", visible_for_submitter=True)
        self.activity.follow_up_activity = self.follow_activity
        self.activity.save()
        self.activity.vehicle_kinds.add(self.vk)
        ActivityFieldRule.objects.filter(activity=self.activity).delete()
        for field_key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
            ActivityFieldRule.objects.create(
                activity=self.activity,
                field_key=field_key,
                mode=ActivityFieldMode.OFF,
            )

    def _base_form_data(self, **overrides):
        data = {
            "name_existing": str(self.name.pk),
            "name_lookup": self.name.value,
            "activity": str(self.activity.pk),
            "vehicle_kind": str(self.vk.pk),
            "waste_type": str(self.wt.pk),
            "suffix": str(self.suf.pk),
            "target_date": self.day.isoformat(),
            "address_value": self.address.value,
            "facility_address_value": "",
            "contact_phone": "",
            "contact_note": "",
            "note": "",
            "has_follow_up": "on",
            "follow_up_activity": str(self.follow_activity.pk),
            "follow_up_target_date": "",
            "is_recurring": "",
            "requires_advance_invoice": "",
        }
        data.update(overrides)
        return data

    def test_form_accepts_follow_up_without_date(self):
        form = CustomerRequestForm(self._base_form_data())
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_form_rejects_follow_up_date_before_target(self):
        form = CustomerRequestForm(
            self._base_form_data(follow_up_target_date=self.day.isoformat()),
        )
        self.assertFalse(form.is_valid())
        self.assertIn("follow_up_target_date", form.errors)

    def test_dispatcher_can_set_follow_up_date(self):
        cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            has_follow_up=True,
            follow_up_activity=self.follow_activity,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        )
        client = Client()
        client.force_login(self.dispecer)
        response = client.post(
            reverse("waste_docs:customer_request_set_follow_up_date", kwargs={"pk": cr.pk}),
            {"follow_up_target_date": self.follow_day.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        cr.refresh_from_db()
        self.assertEqual(cr.follow_up_target_date, self.follow_day)
