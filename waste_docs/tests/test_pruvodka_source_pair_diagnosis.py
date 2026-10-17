"""Diagnostika a sync řádku matice u jízdy."""

from __future__ import annotations

from datetime import date
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
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
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_source_pair_diagnosis import (
    diagnose_pruvodka_source_pair,
    sync_pruvodka_source_pair,
)


class PruvodkaSourcePairDiagnosisTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.user = User.objects.create_user("diag_pair", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Subjekt diag")
        self.ico = IcoCatalog.objects.create(value="99887766")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)

        self.wt = WasteTypeCatalog.objects.create(code="200302", value="W diag")
        self.suf_both = SuffixCatalog.objects.create(value="S-DIAG")

        self.vk_retez = VehicleKindCatalog.objects.create(name="Řetěz diag", shortcut="R", sort_order=1)
        clear_vehicle_kind_compatibility_cache()

        self.rz_retez = VehicleRzCatalog.objects.create(value="RETEZDIAG")
        prof_r = VehicleRzProfile.objects.create(rz=self.rz_retez)
        prof_r.vehicle_kinds.add(self.vk_retez)

        self.pair_hak = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf_both,
            sort_order=0,
        )
        self.pair_hak.yard_vehicle_kinds.add(
            VehicleKindCatalog.objects.create(name="Hák diag", shortcut="H", sort_order=10)
        )

        self.pair_retez = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf_both,
            sort_order=1,
        )
        self.pair_retez.yard_vehicle_kinds.add(self.vk_retez)

        self.activity = ActivityCatalog.objects.create(name="Jízda diag")
        self.address = AddressCatalog.objects.create(value="Addr diag")
        self.waste_code = WasteCodeCatalog.objects.create(value="200302")
        self.waste_category = WasteCategoryCatalog.objects.create(value="20")

    def _ride(self, *, stored_pair=None) -> Pruvodka:
        return Pruvodka.objects.create(
            activity=self.activity,
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self.waste_code,
            waste_category=self.waste_category,
            suffix=self.suf_both,
            vehicle_rz=self.rz_retez,
            source_waste_suffix_pair=stored_pair,
            drive_date=date(2026, 7, 2),
            created_by=self.user,
        )

    def test_diagnose_resolves_retez_without_stored_fk(self):
        ride = self._ride(stored_pair=None)
        diag = diagnose_pruvodka_source_pair(ride)

        self.assertEqual(diag["status"], "missing_stored")
        self.assertEqual(diag["resolved_pair_id"], self.pair_retez.pk)
        self.assertIsNone(diag["stored_pair_id"])
        self.assertEqual(len(diag["candidates"]), 2)
        resolved_rows = [c for c in diag["candidates"] if c["is_resolved"]]
        self.assertEqual(len(resolved_rows), 1)
        self.assertEqual(resolved_rows[0]["pk"], self.pair_retez.pk)

    def test_diagnose_mismatch_when_stored_hak(self):
        ride = self._ride(stored_pair=self.pair_hak)
        diag = diagnose_pruvodka_source_pair(ride)

        self.assertEqual(diag["status"], "mismatch")
        self.assertEqual(diag["stored_pair_id"], self.pair_hak.pk)
        self.assertEqual(diag["resolved_pair_id"], self.pair_retez.pk)
        self.assertEqual(diag["effective_pair_id"], self.pair_hak.pk)

    def test_sync_fixes_missing_and_mismatch(self):
        ride = self._ride(stored_pair=None)
        self.assertTrue(sync_pruvodka_source_pair(ride))
        ride.refresh_from_db()
        self.assertEqual(ride.source_waste_suffix_pair_id, self.pair_retez.pk)

        ride.source_waste_suffix_pair = self.pair_hak
        ride.save(update_fields=["source_waste_suffix_pair"])
        self.assertTrue(sync_pruvodka_source_pair(ride))
        ride.refresh_from_db()
        self.assertEqual(ride.source_waste_suffix_pair_id, self.pair_retez.pk)

    def test_diagnose_ok_when_stored_matches(self):
        ride = self._ride(stored_pair=self.pair_retez)
        diag = diagnose_pruvodka_source_pair(ride)
        self.assertEqual(diag["status"], "ok")
        self.assertFalse(sync_pruvodka_source_pair(ride))

    def test_management_command_output(self):
        ride = self._ride(stored_pair=self.pair_retez)
        out = StringIO()
        call_command("diagnose_pruvodka_pair", ride.pk, stdout=out)
        text = out.getvalue()
        self.assertIn(f"jízda #{ride.pk}", text)
        self.assertIn(f"pk {self.pair_retez.pk}", text)
        self.assertIn("Stav: OK", text)

    def test_management_command_fix(self):
        ride = self._ride(stored_pair=self.pair_hak)
        out = StringIO()
        call_command("diagnose_pruvodka_pair", ride.pk, "--fix", stdout=out)
        ride.refresh_from_db()
        self.assertEqual(ride.source_waste_suffix_pair_id, self.pair_retez.pk)
        self.assertIn("Opraveno:", out.getvalue())
