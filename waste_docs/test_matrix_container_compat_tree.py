"""Matice: pasport H + plán RZ H obslouží úkol 3H díky stromu kompatibility."""

from datetime import date

from django.http import QueryDict
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    ContainerPassport,
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
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache

from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_matrix_post_collect import collect_pending_svoz_matrix_lines


class MatrixContainerCompatTreeTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        self.target = date(2026, 6, 1)
        name = NameCatalog.objects.create(value="Compat tree yard")
        self.subject = NameSubjectProfile.objects.create(name=name, company_name="CT")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák CT", shortcut="H", sort_order=0)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="3H CT",
            shortcut="3H",
            sort_order=1,
            parent_kind=self.vk_h,
        )
        clear_vehicle_kind_compatibility_cache()
        self.wt = WasteTypeCatalog.objects.create(code="TCT", value="Textil")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.activity = ActivityCatalog.objects.create(name="Svoz CT")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk_3h,
            yard_svoz_activity=self.activity,
            yard_svoz_display_label="Textil 3H",
        )
        self.driver = DriverProfile.objects.create(personal_number="CT-1", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="CTRZ")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk_h)
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk_3h,
            sort_order=0,
        )
        ContainerPassport.objects.create(
            container_number="614",
            vehicle_kind=self.vk_h,
            color="—",
        )

    def test_collect_allows_passport_h_for_matrix_row_3h(self):
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "614"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(errs, [], msg=str(errs))
        self.assertEqual(len(pending), 1)
