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
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER, ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm
from waste_docs.models import Pruvodka
from waste_docs.services.customer_request_dispatch import link_customer_request_to_pruvodka
from waste_docs.services.customer_request_follow_up_spawn import spawn_follow_up_customer_request
from waste_docs.services.customer_request_status.ride_state import follow_up_required


class CustomerRequestFollowUpSpawnTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("cr_spawn_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.zadavatel = User.objects.create_user("cr_spawn_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2038, 5, 10)
        self.follow_day = self.day + timedelta(days=2)

        self.name = NameCatalog.objects.create(value="Subjekt spawn")
        self.ico = IcoCatalog.objects.create(value="99887766")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Spawn, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200401", value="W spawn")
        self.suf = SuffixCatalog.objects.create(value="S")
        self.vk = VehicleKindCatalog.objects.create(name="Hák spawn", shortcut="Hs", sort_order=0)

        self.follow_activity = ActivityCatalog.objects.create(name="Stáhnout spawn", visible_for_submitter=True)
        self.activity = ActivityCatalog.objects.create(name="Přistavit spawn", visible_for_submitter=True)
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
            "follow_up_target_date": self.follow_day.isoformat(),
            "is_recurring": "",
            "requires_advance_invoice": "",
        }
        data.update(overrides)
        return data

    def test_create_with_follow_up_spawns_child_request(self):
        client = Client()
        client.force_login(self.zadavatel)
        before = CustomerRequest.objects.count()
        response = client.post(reverse("waste_docs:customer_request_create"), self._base_form_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerRequest.objects.count(), before + 2)

        parent = CustomerRequest.objects.order_by("-pk")[1]
        child = CustomerRequest.objects.order_by("-pk").first()
        self.assertTrue(parent.has_follow_up)
        self.assertEqual(child.follow_up_parent_request_id, parent.pk)
        self.assertEqual(child.activity_id, self.follow_activity.pk)
        self.assertEqual(child.target_date, self.follow_day)
        self.assertFalse(child.has_follow_up)
        self.assertFalse(child.requires_advance_invoice)
        self.assertEqual(child.status, parent.status)
        self.assertEqual(child.created_by_id, parent.created_by_id)

    def test_create_with_follow_up_without_date_spawns_only_parent(self):
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_form_data(follow_up_target_date="")
        before = CustomerRequest.objects.count()
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerRequest.objects.count(), before + 1)
        parent = CustomerRequest.objects.order_by("-pk").first()
        self.assertTrue(parent.has_follow_up)
        self.assertEqual(parent.follow_up_activity_id, self.follow_activity.pk)
        self.assertIsNone(parent.follow_up_target_date)
        self.assertFalse(parent.follow_up_child_requests.exists())

    def test_create_without_follow_up_spawns_single_request(self):
        solo_activity = ActivityCatalog.objects.create(name="Solo spawn", visible_for_submitter=True)
        solo_activity.vehicle_kinds.add(self.vk)
        ActivityFieldRule.objects.filter(activity=solo_activity).delete()
        for field_key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
            ActivityFieldRule.objects.create(
                activity=solo_activity,
                field_key=field_key,
                mode=ActivityFieldMode.OFF,
            )
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_form_data()
        data["activity"] = str(solo_activity.pk)
        data["has_follow_up"] = ""
        data["follow_up_activity"] = ""
        data["follow_up_target_date"] = ""
        before = CustomerRequest.objects.count()
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerRequest.objects.count(), before + 1)

    def test_follow_up_required_false_when_child_exists(self):
        parent = CustomerRequest.objects.create(
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
            follow_up_target_date=self.follow_day,
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
        )
        spawn_follow_up_customer_request(parent=parent, actor=self.zadavatel)
        parent.refresh_from_db()
        self.assertFalse(follow_up_required(parent))

    def test_dispatch_parent_with_child_does_not_open_follow_up_on_pruvodka(self):
        parent = CustomerRequest.objects.create(
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
            follow_up_target_date=self.follow_day,
            status=CustomerRequest.Status.VISIBLE_FOR_DISPATCH,
        )
        spawn_follow_up_customer_request(parent=parent, actor=self.zadavatel)
        pruvodka = Pruvodka.objects.create(
            name=parent.name,
            ico=self.ico,
            activity=parent.activity,
            waste_type=parent.waste_type,
            waste_code=WasteCodeCatalog.objects.create(value="20 04 01"),
            waste_category=WasteCategoryCatalog.objects.create(value="O"),
            suffix=parent.suffix,
            address=parent.address,
            drive_date=parent.target_date,
            created_by=self.dispecer,
        )
        link_customer_request_to_pruvodka(parent, pruvodka, actor=self.dispecer)
        pruvodka.refresh_from_db()
        self.assertFalse(pruvodka.follow_up_open)

    def test_form_valid_without_follow_up(self):
        data = self._base_form_data()
        data["has_follow_up"] = ""
        data["follow_up_activity"] = ""
        data["follow_up_target_date"] = ""
        form = CustomerRequestForm(data, submit_user=self.zadavatel)
        self.assertTrue(form.is_valid(), msg=form.errors)
