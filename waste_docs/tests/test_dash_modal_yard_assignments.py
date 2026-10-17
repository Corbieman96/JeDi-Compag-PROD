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
from waste_docs.services.svoz_dispatch.dash_modal_yard_assignments import (
    plan_row_label_for_assignment,
    yard_driver_assignment_cards_for_date,
)
from waste_docs.services.svoz_dispatch.exception_slot import exception_slot_labels_for_plan
from waste_docs.services.svoz_dispatch.plan import replace_yard_driver_plan_for_date


class DashModalYardAssignmentTests(TestCase):
    def setUp(self):
        self.plan_date = date(2026, 6, 19)
        nm = NameCatalog.objects.create(value="Dash yard nm")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="CZS00720 SD Test")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="Objemný odpad")
        self.suf = SuffixCatalog.objects.create(value="Matrace")
        self.vk = VehicleKindCatalog.objects.create(name="Tříosý Hák", shortcut="3H", sort_order=0)
        self.driver = DriverProfile.objects.create(personal_number="D-01", last_name="Mrňavý", first_name="Aleš")
        self.rz = VehicleRzCatalog.objects.create(value="4SJ5360")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_exception_slot=1,
            yard_svoz_display_label="Objemný odpad Matrace",
        )

    def test_standard_slot_label(self):
        replace_yard_driver_plan_for_date(
            plan_date=self.plan_date,
            standard_rows=[(self.subject.pk, self.vk.pk, [(self.driver.pk, self.rz.pk, "", 1)])],
        )
        row = SvozYardDriverPlan.objects.get(plan_date=self.plan_date)
        labels = exception_slot_labels_for_plan([self.subject.pk])
        self.assertEqual(
            plan_row_label_for_assignment(row, exception_labels=labels),
            "Běžný svoz B1",
        )

    def test_exception_matrix_label_on_card(self):
        replace_yard_driver_plan_for_date(
            plan_date=self.plan_date,
            standard_rows=[],
            exception_pair_slots=[
                (self.subject.pk, self.vk.pk, 0, (self.driver.pk, self.rz.pk, "")),
            ],
        )
        cards = yard_driver_assignment_cards_for_date(self.plan_date)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["yard_name"], "CZS00720 SD Test")
        self.assertEqual(len(cards[0]["assignments"]), 1)
        assignment = cards[0]["assignments"][0]
        self.assertEqual(assignment["plan_label"], "Objemný odpad Matrace")
        self.assertEqual(assignment["driver_label"], "Mrňavý Aleš")
        self.assertEqual(assignment["rz_label"], "4SJ5360")
        self.assertIn("3H", assignment["vehicle_kind_short"] or "")
