"""Perzistence souřadnic bodu z mapy u CustomerRequest (opravný formulář)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

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
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms.customer_request import CustomerRequestForm
from waste_docs.services.customer_request_fix.persist import apply_form_to_request


class CustomerRequestMapPersistenceTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("cr_map_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2038, 9, 1)

        self.name = NameCatalog.objects.create(value="Subjekt mapa CR")
        self.ico = IcoCatalog.objects.create(value="99887766")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Mapa ulice, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200401", value="W mapa")
        self.suf = SuffixCatalog.objects.create(value="KM")
        self.vk = VehicleKindCatalog.objects.create(name="Hák mapa", shortcut="Hm", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz mapa", visible_for_submitter=True)

        meta = waste_type_combo_metadata()
        self.waste_label = meta[str(self.wt.pk)]["label"]

        self.lat = Decimal("50.0833333")
        self.lng = Decimal("14.4166667")

        self.cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.RETURNED_FOR_FIX,
            fulfillment_latitude=self.lat,
            fulfillment_longitude=self.lng,
        )

    def _base_post_data(self, **overrides):
        data = {
            "name_existing": str(self.name.pk),
            "name_lookup": self.name.value,
            "activity": str(self.activity.pk),
            "vehicle_kind": str(self.vk.pk),
            "waste_type": str(self.wt.pk),
            "waste_type_lookup": self.waste_label,
            "suffix": str(self.suf.pk),
            "target_date": self.day.isoformat(),
            "address_value": self.address.value,
            "facility_address_value": "",
            "contact_phone": "",
            "contact_note": "",
            "note": "",
            "has_follow_up": "",
            "follow_up_activity": "",
            "follow_up_target_date": "",
            "is_recurring": "",
            "requires_advance_invoice": "",
            "fulfillment_latitude": str(self.lat),
            "fulfillment_longitude": str(self.lng),
        }
        data.update(overrides)
        return data

    def test_form_initial_loads_coordinates_on_edit(self):
        form = CustomerRequestForm(instance=self.cr)
        self.assertEqual(form.initial["fulfillment_latitude"], self.lat)
        self.assertEqual(form.initial["fulfillment_longitude"], self.lng)

    def test_apply_form_to_request_persists_new_coordinates(self):
        new_lat = Decimal("50.0888888")
        new_lng = Decimal("14.4222222")
        form = CustomerRequestForm(
            data=self._base_post_data(
                fulfillment_latitude=str(new_lat),
                fulfillment_longitude=str(new_lng),
            ),
            instance=self.cr,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = apply_form_to_request(form=form, item=self.cr)
        self.assertEqual(saved.fulfillment_latitude, new_lat)
        self.assertEqual(saved.fulfillment_longitude, new_lng)

    def test_edit_view_renders_saved_coordinates(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "50.0833333")
        self.assertContains(response, "14.4166667")

    def test_edit_view_saves_new_coordinates(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        new_lat = Decimal("50.0999999")
        new_lng = Decimal("14.4333333")
        data = self._base_post_data(
            action="save",
            fulfillment_latitude=str(new_lat),
            fulfillment_longitude=str(new_lng),
        )
        response = client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.fulfillment_latitude, new_lat)
        self.assertEqual(self.cr.fulfillment_longitude, new_lng)
