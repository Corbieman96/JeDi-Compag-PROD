"""Validace druhu vozidla u běžné nové jízdy podle řádku „Povolené odpady a koncovky“.

Když u páru subjekt + odpad + koncovka je nastavený druh vozidla (matice svozu),
musí zvolená RZ tento druh obsloužit. Když u páru žádný druh není, výběr je volný.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
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
from catalogs.models.activity_field_rule import (
    ActivityFieldKey,
    ActivityFieldMode,
    ActivityFieldRule,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka
from waste_docs.zpo_resolved import pair_for_pruvodka


class PruvodkaPairVehicleKindFormTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.user = User.objects.create_user("pair_vk", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt pair vk")
        self.ico = IcoCatalog.objects.create(value="11223344")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)

        self.wt = WasteTypeCatalog.objects.create(code="200302", value="W pair vk")
        self.suf_kinds = SuffixCatalog.objects.create(value="S-KIND")
        self.suf_free = SuffixCatalog.objects.create(value="S-FREE")

        self.vk_atego = VehicleKindCatalog.objects.create(name="Atego pvk", shortcut="A", sort_order=0)
        self.vk_retez = VehicleKindCatalog.objects.create(name="Řetěz pvk", shortcut="R", sort_order=1)
        clear_vehicle_kind_compatibility_cache()

        self.rz_atego = VehicleRzCatalog.objects.create(value="ATEGOPVK")
        prof_a = VehicleRzProfile.objects.create(rz=self.rz_atego)
        prof_a.vehicle_kinds.add(self.vk_atego)

        self.rz_retez = VehicleRzCatalog.objects.create(value="RETEZPVK")
        prof_r = VehicleRzProfile.objects.create(rz=self.rz_retez)
        prof_r.vehicle_kinds.add(self.vk_retez)

        self.activity = ActivityCatalog.objects.create(name="Běžná jízda pvk")
        self.activity.vehicle_kinds.add(self.vk_atego, self.vk_retez)
        ActivityFieldRule.objects.filter(activity=self.activity).delete()
        for field_key in (
            ActivityFieldKey.SND_CISLO,
            ActivityFieldKey.ZPO,
            ActivityFieldKey.DRIVER,
            ActivityFieldKey.FULFILLMENT_ADDRESS,
        ):
            ActivityFieldRule.objects.create(
                activity=self.activity, field_key=field_key, mode=ActivityFieldMode.OFF
            )

        # Pár s nastaveným druhem vozidla (Atego).
        self.pair_kinds = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf_kinds,
        )
        self.pair_kinds.yard_vehicle_kinds.add(self.vk_atego)

        # Pár bez nastaveného druhu vozidla — výběr je volný.
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf_free,
        )

        self.address = AddressCatalog.objects.create(value="Addr pvk")
        self.waste_code = WasteCodeCatalog.objects.create(value="200302")
        self.waste_category = WasteCategoryCatalog.objects.create(value="20")

    def _form_data(self, *, suffix_pk: int, vehicle_rz_pk: int, **overrides):
        data = {
            "activity": str(self.activity.pk),
            "drive_date": "2026-07-02",
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(suffix_pk),
            "vehicle_rz": str(vehicle_rz_pk),
            "fulfillment_address_value": "Ulice, 1, Město",
            "repeat_count": "1",
        }
        data.update(overrides)
        return data

    def test_pair_with_kind_rejects_mismatching_vehicle(self):
        form = PruvodkaForm(
            self._form_data(suffix_pk=self.suf_kinds.pk, vehicle_rz_pk=self.rz_retez.pk),
            user=self.user,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("vehicle_rz", form.errors)

    def test_pair_with_kind_accepts_matching_vehicle(self):
        form = PruvodkaForm(
            self._form_data(suffix_pk=self.suf_kinds.pk, vehicle_rz_pk=self.rz_atego.pk),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_pair_without_kind_accepts_any_vehicle(self):
        form = PruvodkaForm(
            self._form_data(suffix_pk=self.suf_free.pk, vehicle_rz_pk=self.rz_retez.pk),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_multiple_pairs_same_waste_suffix_resolves_by_vehicle_rz(self):
        """Stejný odpad+koncovka, dva řádky (Hák + Řetěz) — validace podle RZ, ne .first()."""
        suf_both = SuffixCatalog.objects.create(value="S-BOTH")
        pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
        )
        pair_hak.yard_vehicle_kinds.add(
            VehicleKindCatalog.objects.create(name="Hák multi", shortcut="H2", sort_order=10)
        )
        pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
        )
        pair_retez.yard_vehicle_kinds.add(self.vk_retez)

        form_retez = PruvodkaForm(
            self._form_data(suffix_pk=suf_both.pk, vehicle_rz_pk=self.rz_retez.pk),
            user=self.user,
        )
        self.assertTrue(form_retez.is_valid(), form_retez.errors)

        form_atego = PruvodkaForm(
            self._form_data(suffix_pk=suf_both.pk, vehicle_rz_pk=self.rz_atego.pk),
            user=self.user,
        )
        self.assertFalse(form_atego.is_valid())
        self.assertIn("vehicle_rz", form_atego.errors)

    def test_save_persists_resolved_source_pair(self):
        """Po uložení jízdy se zapamatuje správný řádek matice (Řetěz, ne první Hák)."""
        suf_both = SuffixCatalog.objects.create(value="S-PERSIST")
        pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=0,
        )
        pair_hak.yard_vehicle_kinds.add(
            VehicleKindCatalog.objects.create(name="Hák persist", shortcut="HP", sort_order=10)
        )
        pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=1,
        )
        pair_retez.yard_vehicle_kinds.add(self.vk_retez)

        form = PruvodkaForm(
            self._form_data(suffix_pk=suf_both.pk, vehicle_rz_pk=self.rz_retez.pk),
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        ride = form.save(commit=False)
        ride.created_by = self.user
        ride.save()
        self.assertEqual(ride.source_waste_suffix_pair_id, pair_retez.pk)
        self.assertNotEqual(ride.source_waste_suffix_pair_id, pair_hak.pk)

    def test_edit_keeps_stored_source_pair(self):
        """Editace s uloženým párem validuje proti stejnému řádku i po reloadu."""
        suf_both = SuffixCatalog.objects.create(value="S-EDIT")
        pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=0,
        )
        pair_hak.yard_vehicle_kinds.add(
            VehicleKindCatalog.objects.create(name="Hák edit", shortcut="HE", sort_order=10)
        )
        pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=1,
        )
        pair_retez.yard_vehicle_kinds.add(self.vk_retez)

        ride = Pruvodka.objects.create(
            activity=self.activity,
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.waste_code,
            waste_category=self.waste_category,
            suffix=suf_both,
            vehicle_rz=self.rz_retez,
            source_waste_suffix_pair=pair_retez,
            drive_date="2026-07-02",
            created_by=self.user,
        )

        form = PruvodkaForm(
            self._form_data(suffix_pk=suf_both.pk, vehicle_rz_pk=self.rz_retez.pk),
            instance=ride,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.source_waste_suffix_pair_id, pair_retez.pk)
        self.assertNotEqual(updated.source_waste_suffix_pair_id, pair_hak.pk)

    def test_pair_for_pruvodka_uses_stored_pair_not_first(self):
        """ZPO resolver vrátí uložený pár, ne .first() podle pk."""
        suf_both = SuffixCatalog.objects.create(value="S-ZPO")
        pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=0,
        )
        pair_hak.yard_vehicle_kinds.add(
            VehicleKindCatalog.objects.create(name="Hák zpo", shortcut="HZ", sort_order=10)
        )
        pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=suf_both,
            sort_order=1,
        )
        pair_retez.yard_vehicle_kinds.add(self.vk_retez)

        ride = Pruvodka.objects.create(
            activity=self.activity,
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.waste_code,
            waste_category=self.waste_category,
            suffix=suf_both,
            vehicle_rz=self.rz_retez,
            source_waste_suffix_pair=pair_retez,
            drive_date="2026-07-02",
            created_by=self.user,
        )

        resolved = pair_for_pruvodka(ride)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.pk, pair_retez.pk)
        self.assertNotEqual(resolved.pk, pair_hak.pk)
