from django.test import TestCase

from catalogs.forms.name_subject_pairs import NameSubjectWasteSuffixPairForm
from catalogs.models import (
    ActivityCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)


class NameSubjectPairVehicleKindsTests(TestCase):
    def setUp(self):
        self.profile = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Subj VK"),
        )
        self.wt = WasteTypeCatalog.objects.create(code="VK01", value="W")
        self.suffix = SuffixCatalog.objects.create(value="S")
        self.activity = ActivityCatalog.objects.create(name="A")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        self.vk_3h = VehicleKindCatalog.objects.create(name="3H", shortcut="3H")

    def test_form_multiple_kinds_and_sync_fk(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suffix,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
        )
        form = NameSubjectWasteSuffixPairForm(
            data={
                "waste_type": str(self.wt.pk),
                "suffix": str(self.suffix.pk),
                "yard_svoz_enabled": True,
                "yard_vehicle_kinds": [str(self.vk_h.pk), str(self.vk_3h.pk)],
                "yard_svoz_activity": str(self.activity.pk),
                "yard_svoz_auto_assign_driver": True,
            },
            instance=pair,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(set(saved.yard_vehicle_kinds.values_list("pk", flat=True)), {self.vk_h.pk, self.vk_3h.pk})
        self.assertIn(saved.yard_vehicle_kind_id, {self.vk_h.pk, self.vk_3h.pk})

    def test_form_empty_kinds_when_svoz_off(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suffix,
        )
        form = NameSubjectWasteSuffixPairForm(
            data={
                "waste_type": str(self.wt.pk),
                "suffix": str(self.suffix.pk),
                "yard_svoz_enabled": False,
                "yard_vehicle_kinds": [],
            },
            instance=pair,
        )
        self.assertTrue(form.is_valid(), form.errors)
