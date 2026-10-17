"""Validace druhu vozidla na formuláři Požadavek (CustomerRequestForm)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.forms.customer_request import CustomerRequestForm


class CustomerRequestVehicleKindTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("cr_vk", password="pw")
        set_user_role(self.user, ROLE_DISPECER)
        self.day = date(2036, 6, 16)

        self.name = NameCatalog.objects.create(value="Subjekt VK test")
        self.subject = NameSubjectProfile.objects.create(name=self.name)
        self.wt = WasteTypeCatalog.objects.create(code="200401", value="Odpad VK")
        self.suf = SuffixCatalog.objects.create(value="H")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
        )

    def _form(self, **extra):
        data = {
            "name_existing": str(self.name.pk),
            "waste_type": str(self.wt.pk),
            "suffix": str(self.suf.pk),
            "target_date": self.day.isoformat(),
            "address_value": "Ulice, 1, Město",
        }
        data.update(extra)
        return CustomerRequestForm(data, submit_user=self.user)

    def test_vehicle_kind_always_required(self):
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_kind", form.errors)

    def test_pair_without_vehicle_kind_shows_clear_message(self):
        form = self._form(vehicle_kind=str(self.vk.pk))
        self.assertFalse(form.is_valid())
        errs = form.errors.get("vehicle_kind", [])
        self.assertTrue(
            any("Povolené odpady a koncovky" in e for e in errs),
            f"Chybí srozumitelná hláška, errors={errs}",
        )

    def test_pair_with_vehicle_kind_but_none_selected(self):
        self.pair.yard_vehicle_kinds.add(self.vk)
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_kind", form.errors)

    def test_pair_with_vehicle_kind_selected_ok(self):
        self.pair.yard_vehicle_kinds.add(self.vk)
        form = self._form(vehicle_kind=str(self.vk.pk))
        form.is_valid()
        self.assertNotIn("vehicle_kind", form.errors)
