from django.test import TestCase

from catalogs.models import VehicleKindCatalog
from catalogs.services.vehicle_kind_display import format_vehicle_kind_label


class VehicleKindDisplayTests(TestCase):
    def test_display_label(self):
        k = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        self.assertEqual(k.display_label(), "Hák (H)")
        self.assertEqual(str(k), "Hák (H)")
        self.assertEqual(format_vehicle_kind_label(k), "Hák (H)")

    def test_display_label_shortcut_only(self):
        k = VehicleKindCatalog.objects.create(name="", shortcut="3H")
        self.assertEqual(k.display_label(), "3H")
