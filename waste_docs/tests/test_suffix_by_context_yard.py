"""Koncovky a odpady — rozlišení průvodka z dvora vs. svoz (matice)."""

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
from catalogs.services.name_subject_pruvodka_snapshot import subject_snapshot_for_pruvodka
from waste_docs.forms import PruvodkaForm
from waste_docs.suffix_by_context import suffixes_by_context_payload
from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs


class SuffixByContextYardFilterTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Subjekt suffix yard")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Yard suffix",
        )
        self.wt = WasteTypeCatalog.objects.create(code="200304", value="O-suffix")
        self.suf_svoz = SuffixCatalog.objects.create(value="K-svoz")
        self.suf_pruv = SuffixCatalog.objects.create(value="K-pruv")
        self.vk = VehicleKindCatalog.objects.create(name="Hák suf", shortcut="H")
        self.activity = ActivityCatalog.objects.create(name="Činnost suf")

        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_svoz,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_pruv,
            yard_svoz_enabled=False,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

    def test_yard_pruvodka_only_returns_pruvodka_suffix(self):
        payload = suffixes_by_context_payload(
            {
                "waste_type_id": str(self.wt.pk),
                "name_id": str(self.name.pk),
                "yard_pruvodka_only": "1",
            }
        )
        self.assertTrue(payload["ok"])
        suffix_ids = {row["suffix_id"] for row in payload["data"]}
        self.assertIn(self.suf_pruv.pk, suffix_ids)
        self.assertNotIn(self.suf_svoz.pk, suffix_ids)

    def test_yard_svoz_matrix_only_returns_svoz_suffix(self):
        payload = suffixes_by_context_payload(
            {
                "waste_type_id": str(self.wt.pk),
                "name_id": str(self.name.pk),
                "yard_svoz_matrix_only": "1",
            }
        )
        self.assertTrue(payload["ok"])
        suffix_ids = {row["suffix_id"] for row in payload["data"]}
        self.assertIn(self.suf_svoz.pk, suffix_ids)
        self.assertNotIn(self.suf_pruv.pk, suffix_ids)

    def test_collection_yard_suffix_without_explicit_flag_uses_new_date_rows(self):
        """Dispečink na /new/ neposílá yard_pruvodka_only — sběrný dvůr se filtruje sám."""
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()
        payload = suffixes_by_context_payload(
            {
                "waste_type_id": str(self.wt.pk),
                "name_id": str(self.name.pk),
            }
        )
        self.assertTrue(payload["ok"])
        suffix_ids = {row["suffix_id"] for row in payload["data"]}
        self.assertIn(self.suf_pruv.pk, suffix_ids)
        self.assertNotIn(self.suf_svoz.pk, suffix_ids)


class SubjectSnapshotYardFilterTests(TestCase):
    """Snapshot pro sběrný dvůr nesmí nabízet odpady jen ze Svoz (matice)."""

    def setUp(self):
        self.name = NameCatalog.objects.create(value="Dvůr snapshot")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="Yard snap",
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="20 03 07", value="O-snap")
        self.suf_svoz = SuffixCatalog.objects.create(value="K-snap-svoz")
        self.suf_pruv = SuffixCatalog.objects.create(value="K-snap-pruv")
        self.vk = VehicleKindCatalog.objects.create(name="Voz snap", shortcut="V")
        self.activity = ActivityCatalog.objects.create(name="A snap")

        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_svoz,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_pruv,
            yard_svoz_enabled=False,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

    def test_collection_yard_snapshot_excludes_svoz_only_wastes(self):
        snap = subject_snapshot_for_pruvodka(self.subject)
        self.assertEqual(snap["allowed_waste_type_ids"], [self.wt.pk])
        self.assertEqual(len(snap["pair_hints"]), 1)
        self.assertEqual(snap["pair_hints"][0]["suffix_id"], self.suf_pruv.pk)

    def test_svoz_only_yard_snapshot_has_empty_wastes(self):
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=self.subject, yard_svoz_enabled=False
        ).delete()
        snap = subject_snapshot_for_pruvodka(self.subject)
        self.assertEqual(snap["allowed_waste_type_ids"], [])
        self.assertEqual(snap["pair_hints"], [])

    def test_both_svoz_and_pruvodka_hidden_on_new(self):
        """Zaškrtnutá Svoz (matice) vylučuje řádek z /new/ i při zapnuté Průvodce z dvora."""
        wt_both = WasteTypeCatalog.objects.create(code="20 03 08", value="O-both")
        suf_both = SuffixCatalog.objects.create(value="K-both")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt_both,
            suffix=suf_both,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )
        snap = subject_snapshot_for_pruvodka(self.subject)
        self.assertNotIn(wt_both.pk, snap["allowed_waste_type_ids"])
        self.assertFalse(
            yard_new_date_matrix_ready_qs(self.subject)
            .filter(waste_type=wt_both)
            .exists()
        )
        payload = suffixes_by_context_payload(
            {
                "waste_type_id": str(wt_both.pk),
                "name_id": str(self.name.pk),
                "yard_pruvodka_only": "1",
            }
        )
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"], [])


class PruvodkaFormYardWasteTypeQuerysetTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user("yard_wt", password="pw")

        self.name = NameCatalog.objects.create(value="Dvůr WT")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="Dvůr")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_pruvodka = True
        self.subject.yard_settings.save()

        self.wt_svoz = WasteTypeCatalog.objects.create(code="200305", value="O-svoz-only")
        self.wt_pruv = WasteTypeCatalog.objects.create(code="200306", value="O-pruv-only")
        self.suf = SuffixCatalog.objects.create(value="K-wt")
        self.vk = VehicleKindCatalog.objects.create(name="Voz WT", shortcut="V")
        self.activity = ActivityCatalog.objects.create(name="A WT")

        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_svoz,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_pruv,
            suffix=self.suf,
            yard_svoz_enabled=False,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

    def test_yard_standalone_waste_type_queryset_excludes_svoz_only(self):
        from unittest.mock import patch

        with patch(
            "waste_docs.forms.pruvodka.get_sberny_dvur_subject",
            return_value=self.subject,
        ), patch(
            "waste_docs.forms.pruvodka.is_sberny_dvur_role",
            return_value=True,
        ):
            form = PruvodkaForm(user=self.user, yard_standalone_mode=True)
        wt_pks = set(form.fields["waste_type"].queryset.values_list("pk", flat=True))
        self.assertIn(self.wt_pruv.pk, wt_pks)
        self.assertNotIn(self.wt_svoz.pk, wt_pks)
        self.assertEqual(
            wt_pks,
            set(
                yard_new_date_matrix_ready_qs(self.subject).values_list(
                    "waste_type_id", flat=True
                )
            ),
        )


class SubjectSnapshotNonYardUnchangedTests(TestCase):
    def test_regular_subject_still_lists_all_pair_wastes(self):
        name = NameCatalog.objects.create(value="Běžný subjekt")
        subject = NameSubjectProfile.objects.create(name=name, company_name="Norm")
        wt_a = WasteTypeCatalog.objects.create(code="200401", value="A")
        wt_b = WasteTypeCatalog.objects.create(code="200402", value="B")
        suf = SuffixCatalog.objects.create(value="K-norm")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject, waste_type=wt_a, suffix=suf
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject, waste_type=wt_b, suffix=suf
        )
        snap = subject_snapshot_for_pruvodka(subject)
        self.assertEqual(set(snap["allowed_waste_type_ids"]), {wt_a.pk, wt_b.pk})
