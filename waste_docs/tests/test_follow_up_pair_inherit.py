"""Navazující jízda dědí řádek matice F/P z 1. části při stejném/slučitelném vozidle."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka


class FollowUpPairInheritFormTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.user = User.objects.create_user("fu_pair", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt fu pair")
        self.ico = IcoCatalog.objects.create(value="88776655")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice fu, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200303", value="W fu pair")
        self.suf = SuffixCatalog.objects.create(value="S-FU-PAIR")

        self.vk_a = VehicleKindCatalog.objects.create(name="Atego fu pair", shortcut="A", sort_order=0)
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák fu pair", shortcut="H", sort_order=1)
        clear_vehicle_kind_compatibility_cache()

        self.pair_atego = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            sort_order=1,
        )
        self.pair_atego.yard_vehicle_kinds.add(self.vk_a)

        self.pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            sort_order=0,
        )
        self.pair_hak.yard_vehicle_kinds.add(self.vk_h)

        self.follow_activity = ActivityCatalog.objects.create(name="Stáhnout fu pair")
        self.parent_activity = ActivityCatalog.objects.create(name="Přistavit fu pair")
        self.parent_activity.follow_up_activity = self.follow_activity
        self.parent_activity.save()
        for act in (self.parent_activity, self.follow_activity):
            act.vehicle_kinds.add(self.vk_a, self.vk_h)
            ActivityFieldRule.objects.filter(activity=act).delete()
            for field_key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
                ActivityFieldRule.objects.create(
                    activity=act, field_key=field_key, mode=ActivityFieldMode.OFF
                )

        self.rz_a = VehicleRzCatalog.objects.create(value="8S46830PAIR")
        prof_a = VehicleRzProfile.objects.create(rz=self.rz_a)
        prof_a.vehicle_kinds.add(self.vk_a)

        self.driver = DriverProfile.objects.create(personal_number="FUP1", last_name="Řidič")

        wc = WasteCodeCatalog.objects.create(value="20 03 03")
        wcat = WasteCategoryCatalog.objects.create(value="Nebezpečný")
        self.parent_ride = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 7, 7),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=wc,
            waste_category=wcat,
            suffix=self.suf,
            vehicle_rz=self.rz_a,
            driver=self.driver,
            follow_up_open=True,
            source_waste_suffix_pair=self.pair_atego,
            created_by=self.user,
        )

    def _follow_form_data(self, **overrides):
        data = {
            "activity": str(self.follow_activity.pk),
            "drive_date": "2026-07-08",
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz_a.pk),
            "follow_up_parent": str(self.parent_ride.pk),
            "fulfillment_address_value": "Ulice fu, 1, Město",
            "repeat_count": "1",
        }
        data.update(overrides)
        return data

    def test_atego_follow_inherits_parent_pair_despite_hak_row(self):
        form = PruvodkaForm(self._follow_form_data(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._resolved_source_pair.pk, self.pair_atego.pk)

    def test_atego_follow_without_parent_pair_resolves_by_vehicle_rz(self):
        self.parent_ride.source_waste_suffix_pair = None
        self.parent_ride.save(update_fields=["source_waste_suffix_pair"])
        form = PruvodkaForm(self._follow_form_data(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form._resolved_source_pair.pk, self.pair_atego.pk)

    def test_atego_follow_without_parent_pair_skips_hak_row_validation(self):
        """Stejné RZ jako 1. část — bez uloženého páru nesmí spadnout na řádek Hák v matici."""
        self.parent_ride.source_waste_suffix_pair = None
        self.parent_ride.save(update_fields=["source_waste_suffix_pair"])
        form = PruvodkaForm(self._follow_form_data(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("vehicle_rz", form.errors)
