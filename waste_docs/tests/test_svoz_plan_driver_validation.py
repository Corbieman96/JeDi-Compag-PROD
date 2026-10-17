"""Validace řidičů při ukládání plánu svozů — sloty s váhou (poměr 1:3)."""

from datetime import date

from django.test import TestCase

from catalogs.models import (
    DriverProfile,
    NameCatalog,
    NameSubjectProfile,
    VehicleKindCatalog,
    VehicleRzCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile

from waste_docs.services.svoz_dispatch.driver_vehicle_kind import (
    validate_plan_drivers_for_vehicle_kinds,
)


class SvozPlanDriverValidationTests(TestCase):
    def setUp(self):
        self.plan_date = date(2032, 6, 11)
        nm = NameCatalog.objects.create(value="Plan validation nm")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Validation yard")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.vk = VehicleKindCatalog.objects.create(name="Vk val", shortcut="VV", sort_order=0)
        self.driver1 = DriverProfile.objects.create(personal_number="VAL-01", last_name="B1")
        self.driver2 = DriverProfile.objects.create(personal_number="VAL-02", last_name="B2")
        self.driver1.allowed_vehicle_kinds.add(self.vk)
        self.driver2.allowed_vehicle_kinds.add(self.vk)
        self.rz1 = VehicleRzCatalog.objects.create(value="VALRZ1")
        self.rz2 = VehicleRzCatalog.objects.create(value="VALRZ2")
        prof1 = VehicleRzProfile.objects.create(rz=self.rz1)
        prof2 = VehicleRzProfile.objects.create(rz=self.rz2)
        prof1.vehicle_kinds.add(self.vk)
        prof2.vehicle_kinds.add(self.vk)

    def test_validate_accepts_four_tuple_slots_with_assignment_weight(self):
        """POST plánu s poměrem 1:3 nesmí spadnout na rozbalení slotů."""
        standard_rows = [
            (
                self.subject.pk,
                self.vk.pk,
                [
                    (self.driver1.pk, self.rz1.pk, "", 1),
                    (self.driver2.pk, self.rz2.pk, "", 3),
                ],
            ),
        ]
        err = validate_plan_drivers_for_vehicle_kinds(
            plan_date=self.plan_date,
            yard_ids=[self.subject.pk],
            standard_rows=standard_rows,
            exception_rows=[],
        )
        self.assertIsNone(err)
