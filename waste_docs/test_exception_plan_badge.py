"""Text badge a seskupení výjimek na plánu svozů."""

from django.test import TestCase

from catalogs.models import VehicleKindCatalog

from waste_docs.services.svoz_dispatch.exception_slot import (
    exception_plan_badge_summary,
    group_exception_sections_by_vehicle_kind,
)


class ExceptionPlanBadgeTests(TestCase):
    def setUp(self):
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(name="Tříosý Hák", shortcut="3H", sort_order=2)

    def _section(self, *, label: str, vk, pair_id: int = 1):
        return {
            "pair_id": pair_id,
            "label": label,
            "slot": 1,
            "vehicle_kind": vk,
            "vehicle_kind_id": vk.pk,
            "driver_id": None,
            "vehicle_rz_id": None,
        }

    def test_badge_sever_like_yard_not_flat_matrix_count(self):
        sections = [
            self._section(label="Objemný odpad Matrace", vk=self.vk_h, pair_id=106),
            self._section(label="Objemný odpad Matrace", vk=self.vk_h, pair_id=109),
            self._section(label="Sever Lisovací", vk=self.vk_3h, pair_id=210),
        ]
        summary = exception_plan_badge_summary(
            sections,
            kind_section_vk_ids=[self.vk_h.pk],
        )
        self.assertIn("Běžný svoz + výjimky:", summary)
        self.assertIn("H (2× Objemný odpad Matrace)", summary)
        self.assertIn("3H (Sever Lisovací)", summary)
        self.assertNotIn("výjimkový řádek matice", summary)

    def test_3h_group_follows_h_even_without_kind_section(self):
        sections = [
            self._section(label="Objemný odpad Matrace", vk=self.vk_h, pair_id=106),
            self._section(label="Sever Lisovací", vk=self.vk_3h, pair_id=210),
        ]
        groups = group_exception_sections_by_vehicle_kind(
            sections,
            kind_section_vk_ids=[self.vk_h.pk],
        )
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["vehicle_kind_id"], self.vk_h.pk)
        self.assertEqual(groups[1]["vehicle_kind_id"], self.vk_3h.pk)
        self.assertEqual(len(groups[0]["sections"]), 1)
        self.assertEqual(len(groups[1]["sections"]), 1)
        self.assertEqual(groups[1]["group_title"], f"{self.vk_3h.display_label()} — výjimky")
        self.assertNotIn("bound method", groups[1]["group_title"])
