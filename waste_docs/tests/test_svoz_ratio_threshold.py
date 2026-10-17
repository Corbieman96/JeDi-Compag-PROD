"""Testy prahu pro aktivaci poměru řidičů B1–B4."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest import TestCase

from django.contrib.auth import get_user_model
from django.test import Client, TestCase as DjangoTestCase
from django.urls import reverse

from catalogs.models import (
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
from waste_docs.services.svoz_dispatch.ratio_threshold import (
    ratio_applies,
    ratio_inactive_hint,
    ratio_min_containers_for_yard,
    weights_for_plan_slots,
)
from waste_docs.services.svoz_dispatch.weighted_assignment import pick_weighted_assignment


class RatioThresholdUnitTests(TestCase):
    def test_ratio_min_defaults_to_five(self):
        self.assertEqual(ratio_min_containers_for_yard(None), 5)

    def test_ratio_min_from_yard_settings(self):
        settings = SimpleNamespace(yard_svoz_ratio_min_containers=7)
        self.assertEqual(ratio_min_containers_for_yard(settings), 7)

    def test_ratio_applies_requires_two_drivers_and_threshold(self):
        self.assertFalse(ratio_applies(filled_driver_count=1, open_task_count=10, ratio_min=5))
        self.assertFalse(ratio_applies(filled_driver_count=2, open_task_count=3, ratio_min=5))
        self.assertTrue(ratio_applies(filled_driver_count=2, open_task_count=5, ratio_min=5))

    def test_weights_inactive_still_stores_ratio(self):
        self.assertEqual(
            weights_for_plan_slots(ratio="2:1", slot_count=2, ratio_active=False),
            [2, 1],
        )

    def test_weights_active_uses_ratio(self):
        self.assertEqual(
            weights_for_plan_slots(ratio="2:1", slot_count=2, ratio_active=True),
            [2, 1],
        )

    def test_inactive_hint_below_threshold(self):
        hint = ratio_inactive_hint(open_task_count=3, ratio_min=5, filled_driver_count=2)
        self.assertIn("Méně než 5", hint)
        self.assertIn("B1", hint)

    def test_inactive_hint_empty_when_active(self):
        self.assertEqual(
            ratio_inactive_hint(open_task_count=6, ratio_min=5, filled_driver_count=2),
            "",
        )


class RatioThresholdWeightedAssignmentTests(TestCase):
    def _row(self, driver_id: int, rz_id: int, sort_order: int, weight: int):
        return SimpleNamespace(
            driver_id=driver_id,
            vehicle_rz_id=rz_id,
            sort_order=sort_order,
            assignment_weight=weight,
        )

    def test_zero_weight_skipped(self):
        rows = [
            self._row(10, 1, 0, 1),
            self._row(20, 2, 1, 0),
        ]
        driver_id, _ = pick_weighted_assignment(rows, {})
        self.assertEqual(driver_id, 10)


class SvozPlanRatioThresholdUiTests(DjangoTestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("ratio_thr_admin", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.admin)
        self.plan_date = date(2032, 9, 1)

        nm = NameCatalog.objects.create(value="Threshold yard")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Threshold dvůr")
        ys = self.subject.yard_settings
        ys.is_collection_yard = True
        ys.yard_svoz_ratio_min_containers = 5
        ys.save()

        self.vk = VehicleKindCatalog.objects.create(name="Vk thr", shortcut="VT", sort_order=0)
        wt = WasteTypeCatalog.objects.create(code="200402", value="W thr")
        sfx = SuffixCatalog.objects.create(value="SFXTHR")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt,
            suffix=sfx,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_auto_assign_driver=True,
        )

        self.driver1 = DriverProfile.objects.create(personal_number="THR-01", last_name="A")
        self.driver2 = DriverProfile.objects.create(personal_number="THR-02", last_name="B")
        self.driver1.allowed_vehicle_kinds.add(self.vk)
        self.driver2.allowed_vehicle_kinds.add(self.vk)
        self.rz1 = VehicleRzCatalog.objects.create(value="THRRZ1")
        self.rz2 = VehicleRzCatalog.objects.create(value="THRRZ2")
        prof1 = VehicleRzProfile.objects.create(rz=self.rz1)
        prof2 = VehicleRzProfile.objects.create(rz=self.rz2)
        prof1.vehicle_kinds.add(self.vk)
        prof2.vehicle_kinds.add(self.vk)

    def _get_plan(self):
        return self.client.get(
            f"{reverse('waste_docs:svoz_dispatch_plan')}?date={self.plan_date.isoformat()}"
        )

    def _create_open_tasks(self, count: int) -> None:
        wt = WasteTypeCatalog.objects.get(code="200402")
        sfx = SuffixCatalog.objects.get(value="SFXTHR")
        for i in range(count):
            SvozTask.objects.create(
                target_date=self.plan_date,
                status=SvozTask.Status.OPEN,
                subject_profile=self.subject,
                created_by=self.admin,
                waste_type=wt,
                suffix=sfx,
                vehicle_kind=self.vk,
                container_numbers=f"C{i + 1}",
            )

    def test_ratio_visible_with_two_drivers_below_threshold(self):
        self._create_open_tasks(3)
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver1,
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
            assignment_weight=1,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver2,
            vehicle_rz=self.rz2,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=1,
            assignment_weight=1,
        )
        response = self._get_plan()
        html = response.content.decode()
        self.assertIn("Méně než 5 požadavků", html)
        self.assertIn('data-open-task-count="3"', html)
        self.assertIn('data-ratio-min="5"', html)
        self.assertNotIn('class="svoz-plan-ratio-wrap svoz-plan-ratio-wrap--hidden"', html)
        self.assertIn(f'name="ratio_{self.subject.pk}_{self.vk.pk}"', html)
        self.assertIn("1 : 1", html)

    def test_ratio_visible_at_threshold(self):
        self._create_open_tasks(5)
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver1,
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
            assignment_weight=2,
        )
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver2,
            vehicle_rz=self.rz2,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=1,
            assignment_weight=1,
        )
        response = self._get_plan()
        html = response.content.decode()
        self.assertNotIn('class="svoz-plan-ratio-wrap svoz-plan-ratio-wrap--hidden"', html)
        self.assertIn(f'name="ratio_{self.subject.pk}_{self.vk.pk}"', html)

    def test_plan_page_shows_ratio_min_input_per_yard(self):
        response = self._get_plan()
        html = response.content.decode()
        self.assertIn(f'name="ratio_min_{self.subject.pk}"', html)
        self.assertIn("Min. požadavků pro poměr", html)
        self.assertIn('class="svoz-plan-yard-ratio-min"', html)

    def test_post_save_persists_custom_ratio_min_on_yard(self):
        post_data = {
            "plan_date": self.plan_date.isoformat(),
            f"ratio_min_{self.subject.pk}": "7",
            f"drv_{self.subject.pk}_{self.vk.pk}_0": str(self.driver1.pk),
            f"vrz_{self.subject.pk}_{self.vk.pk}_0": str(self.rz1.pk),
        }
        response = self.client.post(reverse("waste_docs:svoz_dispatch_plan"), post_data)
        self.assertEqual(response.status_code, 302)
        self.subject.yard_settings.refresh_from_db()
        self.assertEqual(self.subject.yard_settings.yard_svoz_ratio_min_containers, 7)

    def test_post_save_below_threshold_persists_ratio_weights(self):
        self._create_open_tasks(3)
        post_data = {
            "plan_date": self.plan_date.isoformat(),
            f"drv_{self.subject.pk}_{self.vk.pk}_0": str(self.driver1.pk),
            f"vrz_{self.subject.pk}_{self.vk.pk}_0": str(self.rz1.pk),
            f"drv_{self.subject.pk}_{self.vk.pk}_1": str(self.driver2.pk),
            f"vrz_{self.subject.pk}_{self.vk.pk}_1": str(self.rz2.pk),
            f"ratio_{self.subject.pk}_{self.vk.pk}": "2:1",
        }
        response = self.client.post(reverse("waste_docs:svoz_dispatch_plan"), post_data)
        self.assertEqual(response.status_code, 302)
        rows = list(
            SvozYardDriverPlan.objects.filter(
                plan_date=self.plan_date,
                subject_profile=self.subject,
                vehicle_kind=self.vk,
                row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            ).order_by("sort_order")
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].assignment_weight, 2)
        self.assertEqual(rows[1].assignment_weight, 1)
        html = self._get_plan().content.decode()
        self.assertIn('value="2:1" selected', html)

    def test_post_save_at_threshold_persists_ratio_weights(self):
        self._create_open_tasks(5)
        post_data = {
            "plan_date": self.plan_date.isoformat(),
            f"drv_{self.subject.pk}_{self.vk.pk}_0": str(self.driver1.pk),
            f"vrz_{self.subject.pk}_{self.vk.pk}_0": str(self.rz1.pk),
            f"drv_{self.subject.pk}_{self.vk.pk}_1": str(self.driver2.pk),
            f"vrz_{self.subject.pk}_{self.vk.pk}_1": str(self.rz2.pk),
            f"ratio_{self.subject.pk}_{self.vk.pk}": "2:1",
        }
        response = self.client.post(reverse("waste_docs:svoz_dispatch_plan"), post_data)
        self.assertEqual(response.status_code, 302)
        rows = list(
            SvozYardDriverPlan.objects.filter(
                plan_date=self.plan_date,
                subject_profile=self.subject,
                vehicle_kind=self.vk,
                row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            ).order_by("sort_order")
        )
        self.assertEqual(rows[0].assignment_weight, 2)
        self.assertEqual(rows[1].assignment_weight, 1)
        html = self._get_plan().content.decode()
        self.assertIn('value="2:1" selected', html)
