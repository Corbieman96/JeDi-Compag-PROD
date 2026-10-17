"""Ukládání denního plánu svozů — duplicitní řidiči a sloty V1–V4."""

from datetime import date

from django.test import TestCase

from catalogs.models import (
    DriverProfile,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile

from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.exception_slot import plan_assignment_for_exception_pair
from waste_docs.services.svoz_dispatch.plan import (
    replace_yard_driver_plan_for_date,
    validate_plan_driver_uniqueness,
)
from waste_docs.services.svoz_dispatch.plan_coverage import plan_has_driver_for_exception_slot


class ReplaceYardDriverPlanTests(TestCase):
    def setUp(self):
        self.plan_date = date(2032, 5, 20)
        nm = NameCatalog.objects.create(value="Plan replace nm")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Replace yard")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="O repl")
        self.suf = SuffixCatalog.objects.create(value="KR")
        self.vk = VehicleKindCatalog.objects.create(name="Vk repl", shortcut="VR", sort_order=0)
        self.driver = DriverProfile.objects.create(personal_number="RP-01", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="RPRZ1")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_exception_slot=2,
        )

    def test_same_driver_on_v1_and_v2_saves_both_slots(self):
        """Stejný řidič u V1 a V2 (Matrace) — oba sloty musí zůstat v plánu."""
        slots = [
            (self.subject.pk, self.vk.pk, 0, (self.driver.pk, self.rz.pk, "")),
            (self.subject.pk, self.vk.pk, 1, (self.driver.pk, self.rz.pk, "")),
        ]
        self.assertIsNone(
            validate_plan_driver_uniqueness(standard_rows=[], exception_pair_slots=slots)
        )
        replace_yard_driver_plan_for_date(
            plan_date=self.plan_date,
            standard_rows=[],
            exception_pair_slots=slots,
        )
        rows = list(
            SvozYardDriverPlan.objects.filter(
                plan_date=self.plan_date,
                subject_profile=self.subject,
                row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            ).order_by("sort_order")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual({r.sort_order for r in rows}, {0, 1})
        self.assertTrue(all(r.driver_id == self.driver.pk for r in rows))

    def test_exception_v2_only_loads_and_counts_as_covered(self):
        """Jen slot V2 (sort_order=1) — dříve se špatně četl jako ex_list[1] u prázdného V1."""
        replace_yard_driver_plan_for_date(
            plan_date=self.plan_date,
            standard_rows=[],
            exception_pair_slots=[
                (self.subject.pk, self.vk.pk, 1, (self.driver.pk, self.rz.pk, "pozn")),
            ],
        )
        existing_exception = {
            (self.subject.pk, self.vk.pk): {
                1: (self.driver.pk, self.rz.pk, "pozn"),
            }
        }
        did, rz_id, note = plan_assignment_for_exception_pair(self.pair, existing_exception)
        self.assertEqual(did, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)
        self.assertEqual(note, "pozn")
        self.assertTrue(
            plan_has_driver_for_exception_slot(
                plan_date=self.plan_date,
                subject_profile_id=self.subject.pk,
                vehicle_kind_id=self.vk.pk,
                sort_order=1,
            )
        )

    def test_exception_pair_assignment_accepts_four_tuple_slot(self):
        """Po uložení plánu se sloty načítají jako 4-tuple (s assignment_weight)."""
        existing_exception = {
            (self.subject.pk, self.vk.pk): {
                1: (self.driver.pk, self.rz.pk, "pozn", 1),
            }
        }
        did, rz_id, note = plan_assignment_for_exception_pair(self.pair, existing_exception)
        self.assertEqual(did, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)
        self.assertEqual(note, "pozn")
