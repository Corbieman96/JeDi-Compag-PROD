"""Testy matice sběrného dvora a rozlišení průvodka vs. požadavky na svoz."""

from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from waste_docs.yard_matrix import (
    yard_new_date_matrix_ready_qs,
    yard_pruvodka_matrix_rows,
    yard_pruvodka_pair_exists,
    yard_svoz_matrix_row_exists,
    yard_svoz_matrix_rows,
)


class YardPruvodkaPairExistsTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Subjekt Y")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Yard",
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        self.wt = WasteTypeCatalog.objects.create(code="200302", value="O2")
        self.suf = SuffixCatalog.objects.create(value="K")
        self.vk = VehicleKindCatalog.objects.create(name="Nákladní", shortcut="N")
        self.activity = ActivityCatalog.objects.create(name="Svoz činnost")

    def test_svoz_ready_pair_without_yard_pruvodka_flag_is_not_pruvodka_path(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_pruvodka_enabled=False,
        )
        self.assertTrue(yard_svoz_matrix_row_exists(self.subject))
        self.assertFalse(yard_pruvodka_pair_exists(self.subject))

    def test_yard_pruvodka_enabled_with_svoz_activity_counts(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_svoz_activity=self.activity,
        )
        self.assertTrue(yard_pruvodka_pair_exists(self.subject))

    def test_yard_pruvodka_enabled_without_any_activity_does_not_count(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
        )
        self.assertFalse(yard_pruvodka_pair_exists(self.subject))

    def test_yard_pruvodka_enabled_with_dedicated_pruvodka_activity_counts(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_pruvodka_activity=self.activity,
        )
        self.assertTrue(yard_pruvodka_pair_exists(self.subject))


class YardPruvodkaMatrixRowsTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Subjekt rows")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Yard rows",
        )
        self.wt = WasteTypeCatalog.objects.create(code="200303", value="O3")
        self.suf = SuffixCatalog.objects.create(value="L")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        self.activity = ActivityCatalog.objects.create(name="Průvodka činnost")

    def test_svoz_only_row_not_in_pruvodka_matrix(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.assertEqual(yard_pruvodka_matrix_rows(self.subject), [])
        self.assertEqual(len(yard_svoz_matrix_rows(self.subject)), 1)

    def test_pruvodka_enabled_row_in_matrix(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )
        rows = yard_pruvodka_matrix_rows(self.subject)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pk, pair.pk)


class YardNewDateMatrixTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Subjekt new-date")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Yard new-date",
        )
        self.wt = WasteTypeCatalog.objects.create(code="200304", value="O4")
        self.suf = SuffixCatalog.objects.create(value="M")
        self.vk = VehicleKindCatalog.objects.create(name="Vlečka", shortcut="V")
        self.activity = ActivityCatalog.objects.create(name="Činnost new")

    def test_svoz_off_row_in_new_date_matrix(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=False,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )
        rows = list(yard_new_date_matrix_ready_qs(self.subject))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].pk, pair.pk)

    def test_svoz_on_row_excluded_from_new_date_matrix(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.assertEqual(list(yard_new_date_matrix_ready_qs(self.subject)), [])

    def test_both_flags_excluded_from_new_date_matrix(self):
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )
        self.assertEqual(list(yard_new_date_matrix_ready_qs(self.subject)), [])
