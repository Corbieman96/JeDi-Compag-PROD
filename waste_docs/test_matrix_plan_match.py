"""Párování matice sběrného dvora s plánem svozů."""

from datetime import date

from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    DriverProfile,
    IcoCatalog,
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
from waste_docs.services.svoz_dispatch.matrix_plan_match import (
    matrix_pair_resolves_to_plan_assignment,
    planned_driver_and_rz_for_matrix_pair,
)
from waste_docs.services.svoz_dispatch.plan_coverage import plan_has_driver_pool


class MatrixPlanMatchTests(TestCase):
    def setUp(self):
        self.target = date(2031, 6, 10)
        self.name = NameCatalog.objects.create(value="Subjekt plan match")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="Yard Match")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="200303", value="O3")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Sklápěč match", shortcut="SM", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz match")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )
        self.driver = DriverProfile.objects.create(personal_number="MT-01", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="MTRZ01")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk)

    def _make_plan(self, *, vehicle_kind=None, subject=None):
        return SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=subject or self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=vehicle_kind or self.vk,
            sort_order=0,
        )

    def test_planned_assignment_when_plan_exists(self):
        self._make_plan()
        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)
        self.assertTrue(matrix_pair_resolves_to_plan_assignment(self.subject, self.pair, self.target))

    def test_no_assignment_without_plan(self):
        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertIsNone(driver_id)
        self.assertIsNone(rz_id)
        self.assertFalse(matrix_pair_resolves_to_plan_assignment(self.subject, self.pair, self.target))

    def test_plan_has_driver_pool_matches_resolution(self):
        self._make_plan()
        self.assertTrue(
            plan_has_driver_pool(
                plan_date=self.target,
                subject_profile_id=self.subject.pk,
                vehicle_kind_id=self.vk.pk,
                row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            )
        )

    def test_normalized_name_equivalence(self):
        vk_plan_row = VehicleKindCatalog.objects.create(
            name="Rizeny retez eq2",
            shortcut="REQP2",
            sort_order=91,
        )
        vk_matrix = VehicleKindCatalog.objects.create(
            name="Řízený řetěz eq2",
            shortcut="REQM2",
            sort_order=92,
        )
        self._make_plan(vehicle_kind=vk_plan_row)
        self.prof.vehicle_kinds.set([vk_plan_row])

        pair_m = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=WasteTypeCatalog.objects.create(code="299903", value="WtEq2"),
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=vk_matrix,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )
        driver_id, _, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, pair_m, self.target)
        self.assertEqual(driver_id, self.driver.pk)

    def test_planned_assignment_fallback_standard_when_exception_without_slot(self):
        """Výjimka bez slotu V v číselníku — fallback na běžný plán B."""
        self.pair.yard_svoz_auto_assign_driver = False
        self.pair.yard_svoz_exception_slot = None
        self.pair.save(update_fields=["yard_svoz_auto_assign_driver", "yard_svoz_exception_slot"])
        self._make_plan()
        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)

    def test_exception_with_slot_no_fallback_to_standard_plan(self):
        """Výjimka se slotem V1 — bez výjimkového plánu se nepoužije běžný svoz B."""
        self.pair.yard_svoz_auto_assign_driver = False
        self.pair.yard_svoz_exception_slot = 1
        self.pair.save(update_fields=["yard_svoz_auto_assign_driver", "yard_svoz_exception_slot"])
        self._make_plan()
        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertIsNone(driver_id)
        self.assertIsNone(rz_id)

    def test_exception_assignment_uses_configured_v_slot(self):
        """Výjimkový řádek s slotem V2 dostane řidiče z plánu výjimek se sort_order=1."""
        driver_v1 = DriverProfile.objects.create(personal_number="MT-V1", last_name="Slot1")
        driver_v2 = DriverProfile.objects.create(personal_number="MT-V2", last_name="Slot2")
        rz_v1 = VehicleRzCatalog.objects.create(value="MTRZ-V1")
        rz_v2 = VehicleRzCatalog.objects.create(value="MTRZ-V2")
        for rz, vk in ((rz_v1, self.vk), (rz_v2, self.vk)):
            prof = VehicleRzProfile.objects.create(rz=rz)
            prof.vehicle_kinds.add(vk)

        self.pair.yard_svoz_auto_assign_driver = False
        self.pair.yard_svoz_exception_slot = 2
        self.pair.save(update_fields=["yard_svoz_auto_assign_driver", "yard_svoz_exception_slot"])

        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=driver_v1,
            vehicle_rz=rz_v1,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=driver_v2,
            vehicle_rz=rz_v2,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=1,
        )

        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, driver_v2.pk)
        self.assertEqual(rz_id, rz_v2.pk)

    def test_exception_v2_uses_v1_plan_when_v2_slot_empty(self):
        """Plán jen V1 — řádek matice na V2 dostane řidiče z vyplněného V1."""
        driver_v1 = DriverProfile.objects.create(personal_number="MT-V1b", last_name="Slot1b")
        rz_v1 = VehicleRzCatalog.objects.create(value="MTRZ-V1b")
        prof = VehicleRzProfile.objects.create(rz=rz_v1)
        prof.vehicle_kinds.add(self.vk)

        self.pair.yard_svoz_auto_assign_driver = False
        self.pair.yard_svoz_exception_slot = 2
        self.pair.save(update_fields=["yard_svoz_auto_assign_driver", "yard_svoz_exception_slot"])

        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=driver_v1,
            vehicle_rz=rz_v1,
            row_kind=SvozYardDriverPlan.RowKind.EXCEPTION,
            vehicle_kind=self.vk,
            sort_order=0,
        )

        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, driver_v1.pk)
        self.assertEqual(rz_id, rz_v1.pk)

    def test_plan_on_partner_subject_same_dispatch_group(self):
        grp = "tst_dispatch_grp_match"
        self.subject.yard_svoz_dispatch_group = grp
        self.subject.yard_settings.save()

        name_b = NameCatalog.objects.create(value="Subjekt B plan match")
        subject_b = NameSubjectProfile.objects.create(name=name_b, company_name="Yard B")
        subject_b.yard_settings.is_collection_yard = True
        subject_b.yard_settings.save()
        subject_b.yard_svoz_dispatch_group = grp
        subject_b.yard_settings.save()

        self._make_plan(subject=subject_b)
        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)

    def test_own_yard_plan_excludes_partner_drivers_same_dispatch_group(self):
        """Dvůr A má vlastní plán — úkoly A nesmí dostat řidiče z plánu dvora B ve stejné skupině."""
        grp = "tst_dispatch_grp_own_first"
        self.subject.yard_svoz_dispatch_group = grp
        self.subject.yard_settings.save()

        driver_partner = DriverProfile.objects.create(personal_number="MT-PART", last_name="Vrabec")
        rz_partner = VehicleRzCatalog.objects.create(value="MTRZ-PART")
        prof_partner = VehicleRzProfile.objects.create(rz=rz_partner)
        prof_partner.vehicle_kinds.add(self.vk)

        name_b = NameCatalog.objects.create(value="Subjekt partner own first")
        subject_b = NameSubjectProfile.objects.create(name=name_b, company_name="Yard Partner")
        subject_b.yard_settings.is_collection_yard = True
        subject_b.yard_settings.save()
        subject_b.yard_svoz_dispatch_group = grp
        subject_b.yard_settings.save()

        self._make_plan()
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=subject_b,
            driver=driver_partner,
            vehicle_rz=rz_partner,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, self.driver.pk)
        self.assertEqual(rz_id, self.rz.pk)
        self.assertNotEqual(driver_id, driver_partner.pk)

    def test_own_yard_plan_not_mixed_by_shared_ico(self):
        """Stejné IČO nesdílí řidiče — každé SD používá jen vlastní plán."""
        ico = IcoCatalog.objects.create(value="55667788")
        self.subject.ico = ico
        self.subject.save(update_fields=["ico"])

        driver_other = DriverProfile.objects.create(personal_number="MT-ICO", last_name="Jiný")
        rz_other = VehicleRzCatalog.objects.create(value="MTRZ-ICO")
        prof_other = VehicleRzProfile.objects.create(rz=rz_other)
        prof_other.vehicle_kinds.add(self.vk)

        name_b = NameCatalog.objects.create(value="Subjekt ICO yard B")
        subject_b = NameSubjectProfile.objects.create(
            name=name_b,
            company_name="Yard ICO B",
            ico=ico,
        )
        subject_b.yard_settings.is_collection_yard = True
        subject_b.yard_settings.save()

        self._make_plan()
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=subject_b,
            driver=driver_other,
            vehicle_rz=rz_other,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

        driver_id, rz_id, _vk = planned_driver_and_rz_for_matrix_pair(self.subject, self.pair, self.target)
        self.assertEqual(driver_id, self.driver.pk)
        self.assertNotEqual(driver_id, driver_other.pk)
