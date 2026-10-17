"""Řetězec návazností: Přistavení → N× Výměna → Stažení."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka
from waste_docs.services.follow_up_chain import (
    apply_parent_state_after_child_link,
    child_closes_parent_follow_up,
    parent_follow_up_should_stay_open,
    parent_has_terminal_child,
)


class FollowUpChainTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("fu_chain", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt chain")
        self.ico = IcoCatalog.objects.create(value="44556677")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice, 3, Město")
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W chain")
        self.suf = SuffixCatalog.objects.create(value="C")
        self.wc = WasteCodeCatalog.objects.create(value="20 03 01")
        self.wcat = WasteCategoryCatalog.objects.create(value="Ostatní")

        self.stazeni = ActivityCatalog.objects.create(name="Stažení chain")
        self.vymena = ActivityCatalog.objects.create(name="Výměna chain")
        self.pristaveni = ActivityCatalog.objects.create(name="Přistavení chain")
        self.pristaveni.follow_up_activities.add(self.vymena, self.stazeni)
        self.pristaveni.follow_up_terminal_activities.add(self.stazeni)
        self.pristaveni.follow_up_activity = self.stazeni
        self.pristaveni.save()
        self.vk = VehicleKindCatalog.objects.create(name="Hák chain", shortcut="Hc", sort_order=0)
        clear_vehicle_kind_compatibility_cache()
        for act in (self.pristaveni, self.vymena, self.stazeni):
            act.vehicle_kinds.add(self.vk)
        self.rz = VehicleRzCatalog.objects.create(value="RZCHAIN1")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="CH1", last_name="Řidič")
        self._relax_activity_fields(self.pristaveni, self.vymena, self.stazeni)

    def _relax_activity_fields(self, *activities):
        for act in activities:
            ActivityFieldRule.objects.filter(activity=act).delete()
            for key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
                ActivityFieldRule.objects.create(activity=act, field_key=key, mode=ActivityFieldMode.OFF)

    def _create_parent(self) -> Pruvodka:
        return Pruvodka.objects.create(
            activity=self.pristaveni,
            drive_date=date(2026, 4, 1),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_open=True,
            created_by=self.user,
        )

    def test_child_closes_only_terminal(self):
        self.assertFalse(child_closes_parent_follow_up(self.pristaveni, self.vymena.pk))
        self.assertTrue(child_closes_parent_follow_up(self.pristaveni, self.stazeni.pk))

    def test_vymena_keeps_parent_open(self):
        parent = self._create_parent()
        apply_parent_state_after_child_link(parent, self.vymena.pk)
        parent.refresh_from_db()
        self.assertTrue(parent.follow_up_open)
        self.assertIsNone(parent.follow_up_resolved_at)

    def test_stazeni_closes_parent(self):
        parent = self._create_parent()
        apply_parent_state_after_child_link(parent, self.stazeni.pk)
        parent.refresh_from_db()
        self.assertFalse(parent.follow_up_open)
        self.assertIsNotNone(parent.follow_up_resolved_at)

    def test_multiple_vymena_then_stazeni(self):
        parent = self._create_parent()
        v1 = Pruvodka.objects.create(
            activity=self.vymena,
            drive_date=date(2026, 4, 2),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_parent=parent,
            created_by=self.user,
        )
        apply_parent_state_after_child_link(parent, self.vymena.pk)
        v2 = Pruvodka.objects.create(
            activity=self.vymena,
            drive_date=date(2026, 4, 3),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_parent=parent,
            created_by=self.user,
        )
        apply_parent_state_after_child_link(parent, self.vymena.pk)
        parent.refresh_from_db()
        self.assertTrue(parent.follow_up_open)
        self.assertFalse(parent_has_terminal_child(parent))

        stazeni = Pruvodka.objects.create(
            activity=self.stazeni,
            drive_date=date(2026, 4, 5),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_parent=parent,
            created_by=self.user,
        )
        apply_parent_state_after_child_link(parent, self.stazeni.pk)
        parent.refresh_from_db()
        self.assertTrue(parent_has_terminal_child(parent))
        self.assertFalse(parent_follow_up_should_stay_open(parent))
        self.assertFalse(parent.follow_up_open)

    def test_form_allows_second_vymena(self):
        parent = self._create_parent()
        Pruvodka.objects.create(
            activity=self.vymena,
            drive_date=date(2026, 4, 2),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_parent=parent,
            created_by=self.user,
        )
        apply_parent_state_after_child_link(parent, self.vymena.pk)
        parent.refresh_from_db()

        data = {
            "activity": str(self.vymena.pk),
            "drive_date": "2026-04-04",
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz.pk),
            "driver": str(self.driver.pk),
            "follow_up_parent": str(parent.pk),
            "fulfillment_address_value": "Ulice, 3, Město",
            "repeat_count": "1",
        }
        form = PruvodkaForm(data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_blocks_second_stazeni(self):
        parent = self._create_parent()
        Pruvodka.objects.create(
            activity=self.stazeni,
            drive_date=date(2026, 4, 6),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            follow_up_parent=parent,
            created_by=self.user,
        )
        apply_parent_state_after_child_link(parent, self.stazeni.pk)

        data = {
            "activity": str(self.stazeni.pk),
            "drive_date": "2026-04-07",
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "follow_up_parent": str(parent.pk),
            "fulfillment_address_value": "Ulice, 3, Město",
            "repeat_count": "1",
        }
        form = PruvodkaForm(data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("follow_up_parent", form.errors)

    def test_infer_terminal_excludes_vymena_without_explicit_config(self):
        act = ActivityCatalog.objects.create(name="Přistavení infer")
        v = ActivityCatalog.objects.create(name="Výměna infer")
        s = ActivityCatalog.objects.create(name="Stažení infer")
        act.follow_up_activities.add(v, s)
        act.save()
        from waste_docs.services.follow_up_chain import terminal_follow_up_activity_ids

        terminal_ids = terminal_follow_up_activity_ids(act)
        self.assertIn(s.pk, terminal_ids)
        self.assertNotIn(v.pk, terminal_ids)


class FollowUpChainCreateViewTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("fu_chain_view", password="pw", is_superuser=True)
        self.client = Client()
        self.client.login(username="fu_chain_view", password="pw")

        self.name = NameCatalog.objects.create(value="Subjekt chain view")
        self.ico = IcoCatalog.objects.create(value="55664433")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice, 4, Město")
        self.wt = WasteTypeCatalog.objects.create(code="200302", value="W chain v")
        self.suf = SuffixCatalog.objects.create(value="D")
        self.wc = WasteCodeCatalog.objects.create(value="20 03 02")
        self.wcat = WasteCategoryCatalog.objects.create(value="Směsný")

        self.stazeni = ActivityCatalog.objects.create(name="Stažení chain v")
        self.vymena = ActivityCatalog.objects.create(name="Výměna chain v")
        self.pristaveni = ActivityCatalog.objects.create(name="Přistavení chain v")
        self.pristaveni.follow_up_activities.add(self.vymena, self.stazeni)
        self.pristaveni.follow_up_terminal_activities.add(self.stazeni)
        self.pristaveni.save()
        self.vk = VehicleKindCatalog.objects.create(name="Hák chain v", shortcut="Hv", sort_order=0)
        clear_vehicle_kind_compatibility_cache()
        for act in (self.pristaveni, self.vymena, self.stazeni):
            act.vehicle_kinds.add(self.vk)
        self.rz = VehicleRzCatalog.objects.create(value="RZCHAIN2")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="CH2", last_name="Řidič")
        self._relax_activity_fields(self.pristaveni, self.vymena, self.stazeni)
        self.parent = Pruvodka.objects.create(
            activity=self.pristaveni,
            drive_date=date(2026, 5, 1),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.wc,
            waste_category=self.wcat,
            suffix=self.suf,
            vehicle_rz=self.rz,
            driver=self.driver,
            follow_up_open=True,
            created_by=self.user,
        )

    def _relax_activity_fields(self, *activities):
        for act in activities:
            ActivityFieldRule.objects.filter(activity=act).delete()
            for key in (ActivityFieldKey.SND_CISLO, ActivityFieldKey.ZPO):
                ActivityFieldRule.objects.create(activity=act, field_key=key, mode=ActivityFieldMode.OFF)

    def test_create_vymena_via_post_keeps_parent_open(self):
        response = self.client.post(
            reverse("waste_docs:create"),
            {
                "activity": str(self.vymena.pk),
                "drive_date": "2026-05-02",
                "waste_type": str(self.wt.pk),
                "name": str(self.name.pk),
                "ico": str(self.ico.pk),
                "suffix": str(self.suf.pk),
                "vehicle_rz": str(self.rz.pk),
                "driver": str(self.driver.pk),
                "follow_up_parent": str(self.parent.pk),
                "fulfillment_address_value": "Ulice, 4, Město",
                "repeat_count": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.follow_up_open)
