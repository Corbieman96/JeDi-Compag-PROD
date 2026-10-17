"""Round-robin přiřazení více řidičů z plánu pro stejný druh vozidla."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
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

from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import assign_driver_for_new_task


class SvozPlanRoundRobinTests(TestCase):
    def setUp(self):
        self.day = date(2032, 1, 10)
        User = get_user_model()
        self.actor = User.objects.create_user("rr_user", password="pw")
        name = NameCatalog.objects.create(value="RR yard")
        self.subject = NameSubjectProfile.objects.create(name=name, company_name="RR")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="RR01", value="W")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="VK RR", shortcut="VR", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz RR")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
        )
        self.d1 = DriverProfile.objects.create(personal_number="RR-1", last_name="První")
        self.d2 = DriverProfile.objects.create(personal_number="RR-2", last_name="Druhý")
        self.rz1 = VehicleRzCatalog.objects.create(value="RRRZ1")
        self.rz2 = VehicleRzCatalog.objects.create(value="RRRZ2")
        p1 = VehicleRzProfile.objects.create(rz=self.rz1)
        p2 = VehicleRzProfile.objects.create(rz=self.rz2)
        p1.vehicle_kinds.add(self.vk)
        p2.vehicle_kinds.add(self.vk)
        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.d1,
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.day,
            subject_profile=self.subject,
            driver=self.d2,
            vehicle_rz=self.rz2,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=1,
        )

    def test_second_task_gets_second_driver(self):
        t1 = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="1",
            target_date=self.day,
        )
        assign_driver_for_new_task(t1, self.pair, actor=self.actor)
        t1.refresh_from_db()
        self.assertEqual(t1.assigned_driver_id, self.d1.pk)

        t2 = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="2",
            target_date=self.day,
        )
        assign_driver_for_new_task(t2, self.pair, actor=self.actor)
        t2.refresh_from_db()
        self.assertEqual(t2.assigned_driver_id, self.d2.pk)
