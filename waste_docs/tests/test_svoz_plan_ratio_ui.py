"""UI plánu svozů — poměr B1–B4 se vykresluje vždy, skrytý dokud nejsou 2 řidiči."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
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
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.svoz_dispatch.ratio_quotas import build_svoz_ratio_client_config


class SvozPlanRatioUiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("ratio_ui_admin", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.admin)
        self.plan_date = date(2032, 8, 1)

        nm = NameCatalog.objects.create(value="Ratio UI yard")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Ratio UI dvůr")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.vk = VehicleKindCatalog.objects.create(name="Vk ratio", shortcut="VR", sort_order=0)
        wt = WasteTypeCatalog.objects.create(code="200401", value="W ratio")
        sfx = SuffixCatalog.objects.create(value="SFXRAT")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt,
            suffix=sfx,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_auto_assign_driver=True,
        )

        self.driver1 = DriverProfile.objects.create(personal_number="RAT-01", last_name="A")
        self.driver2 = DriverProfile.objects.create(personal_number="RAT-02", last_name="B")
        self.driver1.allowed_vehicle_kinds.add(self.vk)
        self.driver2.allowed_vehicle_kinds.add(self.vk)
        self.rz1 = VehicleRzCatalog.objects.create(value="RATRZ1")
        self.rz2 = VehicleRzCatalog.objects.create(value="RATRZ2")
        prof1 = VehicleRzProfile.objects.create(rz=self.rz1)
        prof2 = VehicleRzProfile.objects.create(rz=self.rz2)
        prof1.vehicle_kinds.add(self.vk)
        prof2.vehicle_kinds.add(self.vk)

    def _get_plan(self):
        return self.client.get(
            f"{reverse('waste_docs:svoz_dispatch_plan')}?date={self.plan_date.isoformat()}"
        )

    def test_ratio_wrap_always_in_html_hidden_with_one_driver(self):
        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.driver1,
            vehicle_rz=self.rz1,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        response = self._get_plan()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="svoz-plan-ratio-wrap svoz-plan-ratio-wrap--hidden"', html)
        self.assertIn('id="svoz-ratio-config"', html)
        config = response.context["svoz_ratio_config"]
        self.assertEqual(config, build_svoz_ratio_client_config())
        self.assertIn("1:1", config["presets"]["2"])

    def test_ratio_wrap_visible_with_two_saved_drivers_and_enough_tasks(self):
        from waste_docs.models import SvozTask

        wt = WasteTypeCatalog.objects.get(code="200401")
        sfx = SuffixCatalog.objects.get(value="SFXRAT")
        User = get_user_model()
        admin = User.objects.get(username="ratio_ui_admin")
        for i in range(5):
            SvozTask.objects.create(
                target_date=self.plan_date,
                status=SvozTask.Status.OPEN,
                subject_profile=self.subject,
                created_by=admin,
                waste_type=wt,
                suffix=sfx,
                vehicle_kind=self.vk,
                container_numbers=f"R{i + 1}",
            )
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
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('data-last-driver-count="2"', html)
        self.assertNotIn('class="svoz-plan-ratio-wrap svoz-plan-ratio-wrap--hidden"', html)
        self.assertRegex(
            html,
            rf'<div class="svoz-plan-ratio-wrap"[^>]*data-yard="{self.subject.pk}"',
        )
        self.assertIn(f'name="ratio_{self.subject.pk}_{self.vk.pk}"', html)
