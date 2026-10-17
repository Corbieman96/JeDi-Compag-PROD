"""Plán svozů — běžný svoz vs výjimky podle číselníku F/P."""

from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from waste_docs.services.svoz_dispatch.exception_slot import exception_matrix_pairs_by_yard
from waste_docs.services.svoz_dispatch.plan_coverage import vehicle_kinds_by_yard


class SvozPlanCatalogModelTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="SD plán katalog")
        self.ico = IcoCatalog.objects.create(value="47551986")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="SD Plán katalog",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(name="Tříosý Hák", shortcut="3H", sort_order=2)
        self.activity = ActivityCatalog.objects.create(name="Svoz katalog test")
        self.wt_std = WasteTypeCatalog.objects.create(code="200101", value="Lisovací std")
        self.wt_exc = WasteTypeCatalog.objects.create(code="200110", value="Matrace exc")
        self.suf = SuffixCatalog.objects.create(value="KV-CAT")

        self.standard_pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_std,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
            yard_vehicle_kind=self.vk_h,
        )
        self.standard_pair.yard_vehicle_kinds.set([self.vk_h, self.vk_3h])

        self.exception_pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_exc,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind=self.vk_h,
            yard_svoz_exception_slot=1,
            yard_svoz_display_label="Objemný Matrace",
        )

        self.exception_no_slot = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=WasteTypeCatalog.objects.create(code="209999", value="Bez slotu"),
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=False,
            yard_vehicle_kind=self.vk_h,
        )

    def test_vehicle_kinds_from_m2m_only_3h(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=WasteTypeCatalog.objects.create(code="201111", value="Jen 3H M2M"),
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_svoz_auto_assign_driver=True,
            yard_vehicle_kind=None,
        )
        pair.yard_vehicle_kinds.set([self.vk_3h])
        kinds = vehicle_kinds_by_yard([self.subject.pk])[self.subject.pk]
        shortcuts = {k.shortcut for k in kinds}
        self.assertIn("3H", shortcuts)

    def test_vehicle_kinds_from_standard_rows_includes_h_and_3h(self):
        kinds = vehicle_kinds_by_yard([self.subject.pk])[self.subject.pk]
        shortcuts = {k.shortcut for k in kinds}
        self.assertIn("H", shortcuts)
        self.assertIn("3H", shortcuts)

    def test_exception_rows_only_with_v_slot(self):
        by_yard = exception_matrix_pairs_by_yard([self.subject.pk])
        rows = by_yard.get(self.subject.pk, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "Objemný Matrace")
        self.assertEqual(rows[0]["slot"], 1)
