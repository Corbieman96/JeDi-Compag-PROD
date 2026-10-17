from django.test import TestCase

from catalogs.forms.vehicle_rz import VehicleKindCatalogForm
from catalogs.models import VehicleKindCatalog
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache


class VehicleKindCatalogFormTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()

    def test_form_includes_parent_kind(self):
        form = VehicleKindCatalogForm()
        self.assertIn("parent_kind", form.fields)

    def test_save_kind_with_parent(self):
        parent = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        form = VehicleKindCatalogForm(
            data={"name": "Tříosý hák", "shortcut": "3H", "parent_kind": str(parent.pk)}
        )
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save()
        self.assertEqual(obj.parent_kind_id, parent.pk)

    def test_reject_parent_cycle(self):
        parent = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        child = VehicleKindCatalog.objects.create(name="3H", shortcut="3H", parent_kind=parent)
        form = VehicleKindCatalogForm(
            data={"name": "Hák", "shortcut": "H2", "parent_kind": str(child.pk)},
            instance=parent,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("parent_kind", form.errors)
