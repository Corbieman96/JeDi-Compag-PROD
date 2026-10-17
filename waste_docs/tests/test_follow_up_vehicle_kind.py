"""Kontrola druhu vozidla u navazující jízdy — směrová kompatibilita (3H stáhne H, ne naopak)."""

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
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import (
    clear_vehicle_kind_compatibility_cache,
    follow_up_covers_parent_kind,
)
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka
from waste_docs.services.follow_up_vehicle_kind import (
    allowed_follow_kind_ids_for_parent_rz,
    rz_vehicle_kinds_compatible_for_follow_up,
)


class FollowUpVehicleKindServiceTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.vk_a = VehicleKindCatalog.objects.create(name="Atego", shortcut="A", sort_order=0)
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="Tříosý hák",
            shortcut="3H",
            sort_order=2,
            parent_kind=self.vk_h,
        )
        clear_vehicle_kind_compatibility_cache()

        self.rz_a = VehicleRzCatalog.objects.create(value="RZ-ATEGO")
        prof_a = VehicleRzProfile.objects.create(rz=self.rz_a)
        prof_a.vehicle_kinds.add(self.vk_a)

        self.rz_h = VehicleRzCatalog.objects.create(value="RZ-H")
        prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        prof_h.vehicle_kinds.add(self.vk_h)

        self.rz_3h = VehicleRzCatalog.objects.create(value="RZ-3H")
        prof_3h = VehicleRzProfile.objects.create(rz=self.rz_3h)
        prof_3h.vehicle_kinds.add(self.vk_3h)

        self.rz_h3h = VehicleRzCatalog.objects.create(value="RZ-H3H")
        prof_h3h = VehicleRzProfile.objects.create(rz=self.rz_h3h)
        prof_h3h.vehicle_kinds.add(self.vk_h, self.vk_3h)

        self.vk_o = VehicleKindCatalog.objects.create(name="Odtah", shortcut="O", sort_order=3)
        clear_vehicle_kind_compatibility_cache()
        self.rz_hao = VehicleRzCatalog.objects.create(value="2SD4670")
        prof_hao = VehicleRzProfile.objects.create(rz=self.rz_hao)
        prof_hao.vehicle_kinds.add(self.vk_h, self.vk_a, self.vk_o)

    def test_follow_up_covers_parent_kind_matrix(self):
        self.assertTrue(follow_up_covers_parent_kind(self.vk_a.pk, self.vk_a.pk))
        self.assertFalse(follow_up_covers_parent_kind(self.vk_a.pk, self.vk_h.pk))
        self.assertFalse(follow_up_covers_parent_kind(self.vk_a.pk, self.vk_3h.pk))

        self.assertTrue(follow_up_covers_parent_kind(self.vk_h.pk, self.vk_h.pk))
        self.assertTrue(follow_up_covers_parent_kind(self.vk_h.pk, self.vk_3h.pk))
        self.assertFalse(follow_up_covers_parent_kind(self.vk_3h.pk, self.vk_h.pk))

        self.assertTrue(follow_up_covers_parent_kind(self.vk_3h.pk, self.vk_3h.pk))

    def test_rz_compatible_matrix(self):
        self.assertFalse(rz_vehicle_kinds_compatible_for_follow_up(self.rz_a, self.rz_h))
        self.assertFalse(rz_vehicle_kinds_compatible_for_follow_up(self.rz_a, self.rz_3h))
        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_a, self.rz_a))

        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_h, self.rz_h))
        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_h, self.rz_3h))
        self.assertFalse(rz_vehicle_kinds_compatible_for_follow_up(self.rz_3h, self.rz_h))

        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_h3h, self.rz_h))

    def test_hao_parent_accepts_atego_follow(self):
        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_hao, self.rz_a))
        self.assertTrue(rz_vehicle_kinds_compatible_for_follow_up(self.rz_hao, self.rz_h))
        self.assertFalse(rz_vehicle_kinds_compatible_for_follow_up(self.rz_3h, self.rz_hao))

    def test_allowed_follow_kind_ids_for_parent_h_includes_3h(self):
        allowed = allowed_follow_kind_ids_for_parent_rz(self.rz_h)
        self.assertIn(self.vk_h.pk, allowed)
        self.assertIn(self.vk_3h.pk, allowed)
        self.assertNotIn(self.vk_a.pk, allowed)


class FollowUpVehicleKindFormTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.user = User.objects.create_user("fu_vk", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt fu vk")
        self.ico = IcoCatalog.objects.create(value="99887766")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W fu vk")
        self.suf = SuffixCatalog.objects.create(value="B fu")

        self.vk_a = VehicleKindCatalog.objects.create(name="Atego fu", shortcut="A", sort_order=0)
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák fu", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="3H fu",
            shortcut="3H",
            sort_order=2,
            parent_kind=self.vk_h,
        )
        clear_vehicle_kind_compatibility_cache()

        self.follow_activity = ActivityCatalog.objects.create(name="Stáhnout fu")
        self.parent_activity = ActivityCatalog.objects.create(name="Přistavit fu")
        self.parent_activity.follow_up_activity = self.follow_activity
        self.parent_activity.save()
        for act in (self.parent_activity, self.follow_activity):
            act.vehicle_kinds.add(self.vk_a, self.vk_h, self.vk_3h)
            ActivityFieldRule.objects.filter(activity=act).delete()
            for field_key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
                ActivityFieldRule.objects.create(activity=act, field_key=field_key, mode=ActivityFieldMode.OFF)

        self.rz_a = VehicleRzCatalog.objects.create(value="8S46830FU")
        prof_a = VehicleRzProfile.objects.create(rz=self.rz_a)
        prof_a.vehicle_kinds.add(self.vk_a)

        self.rz_h = VehicleRzCatalog.objects.create(value="9S06217FU")
        prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        prof_h.vehicle_kinds.add(self.vk_h)

        self.rz_3h = VehicleRzCatalog.objects.create(value="3HONLYFU")
        prof_3h = VehicleRzProfile.objects.create(rz=self.rz_3h)
        prof_3h.vehicle_kinds.add(self.vk_3h)

        self.rz_h3h = VehicleRzCatalog.objects.create(value="H3HFU")
        prof_h3h = VehicleRzProfile.objects.create(rz=self.rz_h3h)
        prof_h3h.vehicle_kinds.add(self.vk_h, self.vk_3h)

        self.vk_o = VehicleKindCatalog.objects.create(name="Odtah fu", shortcut="O", sort_order=3)
        clear_vehicle_kind_compatibility_cache()
        self.rz_hao = VehicleRzCatalog.objects.create(value="2SD4670FU")
        prof_hao = VehicleRzProfile.objects.create(rz=self.rz_hao)
        prof_hao.vehicle_kinds.add(self.vk_h, self.vk_a, self.vk_o)
        for act in (self.parent_activity, self.follow_activity):
            act.vehicle_kinds.add(self.vk_o)

        self.driver = DriverProfile.objects.create(personal_number="FU1", last_name="Řidič")

        wc = WasteCodeCatalog.objects.create(value="20 03 01")
        wcat = WasteCategoryCatalog.objects.create(value="Nebezpečný")
        self.parent_ride = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 12),
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
            created_by=self.user,
        )

    def _follow_form_data(self, *, vehicle_rz_pk: int, **overrides):
        data = {
            "activity": str(self.follow_activity.pk),
            "drive_date": "2026-06-14",
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(vehicle_rz_pk),
            "follow_up_parent": str(self.parent_ride.pk),
            "fulfillment_address_value": "Ulice, 1, Město",
            "repeat_count": "1",
        }
        data.update(overrides)
        return data

    def test_atego_parent_rejects_hak_follow(self):
        form = PruvodkaForm(self._follow_form_data(vehicle_rz_pk=self.rz_h.pk), user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_rz", form.errors)

    def test_atego_parent_accepts_atego_follow(self):
        rz_a2 = VehicleRzCatalog.objects.create(value="ATEGO2FU")
        prof = VehicleRzProfile.objects.create(rz=rz_a2)
        prof.vehicle_kinds.add(self.vk_a)
        form = PruvodkaForm(self._follow_form_data(vehicle_rz_pk=rz_a2.pk), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_h_parent_accepts_3h_follow(self):
        parent_h = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 13),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.get(value="20 03 01"),
            waste_category=WasteCategoryCatalog.objects.get(value="Nebezpečný"),
            suffix=self.suf,
            vehicle_rz=self.rz_h,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )
        data = self._follow_form_data(vehicle_rz_pk=self.rz_3h.pk)
        data["follow_up_parent"] = str(parent_h.pk)
        form = PruvodkaForm(data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_3h_parent_rejects_h_follow(self):
        parent_3h = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 15),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.get(value="20 03 01"),
            waste_category=WasteCategoryCatalog.objects.get(value="Nebezpečný"),
            suffix=self.suf,
            vehicle_rz=self.rz_3h,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )
        data = self._follow_form_data(vehicle_rz_pk=self.rz_h.pk)
        data["follow_up_parent"] = str(parent_3h.pk)
        form = PruvodkaForm(data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_rz", form.errors)

    def test_3h_parent_accepts_h_follow_with_manual_override(self):
        parent_3h = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 16),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.get(value="20 03 01"),
            waste_category=WasteCategoryCatalog.objects.get(value="Nebezpečný"),
            suffix=self.suf,
            vehicle_rz=self.rz_3h,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )
        data = self._follow_form_data(vehicle_rz_pk=self.rz_h.pk)
        data["follow_up_parent"] = str(parent_3h.pk)
        data["follow_up_vehicle_rz_manual"] = "on"
        form = PruvodkaForm(data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_init_includes_h_rz_when_manual_override_post(self):
        parent_3h = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 17),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.get(value="20 03 01"),
            waste_category=WasteCategoryCatalog.objects.get(value="Nebezpečný"),
            suffix=self.suf,
            vehicle_rz=self.rz_3h,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )
        data = self._follow_form_data(vehicle_rz_pk=self.rz_h.pk)
        data["follow_up_parent"] = str(parent_3h.pk)
        data["follow_up_vehicle_rz_manual"] = "on"
        form = PruvodkaForm(data, user=self.user)
        rz_ids = set(form.fields["vehicle_rz"].queryset.values_list("pk", flat=True))
        self.assertIn(self.rz_h.pk, rz_ids)

    def test_init_filters_vehicle_rz_for_atego_parent(self):
        form = PruvodkaForm(
            initial={"follow_up_parent": self.parent_ride.pk, "activity": self.follow_activity.pk},
            user=self.user,
        )
        rz_ids = set(form.fields["vehicle_rz"].queryset.values_list("pk", flat=True))
        self.assertIn(self.rz_a.pk, rz_ids)
        self.assertNotIn(self.rz_h.pk, rz_ids)
        self.assertNotIn(self.rz_3h.pk, rz_ids)

    def test_hao_parent_form_accepts_atego_follow(self):
        parent_hao = Pruvodka.objects.create(
            activity=self.parent_activity,
            drive_date=date(2026, 6, 18),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.get(value="20 03 01"),
            waste_category=WasteCategoryCatalog.objects.get(value="Nebezpečný"),
            suffix=self.suf,
            vehicle_rz=self.rz_hao,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )
        data = self._follow_form_data(vehicle_rz_pk=self.rz_a.pk)
        data["follow_up_parent"] = str(parent_hao.pk)
        form = PruvodkaForm(data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
