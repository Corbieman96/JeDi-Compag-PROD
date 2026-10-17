"""Evidence oprav vozidel — měsíční součet a report summary."""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import VehicleRzCatalog, VehicleRzProfile, VehicleRzRepair
from catalogs.services.vehicle_repairs import month_hours_sum
from reports.services.date_range import ReportDateRange
from reports.services.operations_summary import build_operations_summary
from reports.services.vehicle_repairs_summary import build_vehicle_repairs_summary

User = get_user_model()


class VehicleRzRepairTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        self.admin = User.objects.create_superuser("repair_admin", password="pw")
        self.rz_a = VehicleRzCatalog.objects.create(value="1A11111")
        self.rz_b = VehicleRzCatalog.objects.create(value="2B22222")
        self.profile_a = VehicleRzProfile.objects.create(rz=self.rz_a, vehicle_type="Vlek A")
        self.profile_b = VehicleRzProfile.objects.create(rz=self.rz_b, vehicle_type="Vlek B")
        self.client = Client()

    def test_month_hours_sum(self):
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_a,
            repair_date=date(2030, 5, 3),
            hours=Decimal("2.50"),
            note="olej",
            created_by=self.admin,
        )
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_a,
            repair_date=date(2030, 5, 20),
            hours=Decimal("1.25"),
            note="brzdy",
            created_by=self.admin,
        )
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_a,
            repair_date=date(2030, 6, 1),
            hours=Decimal("9.00"),
            note="mimo měsíc",
            created_by=self.admin,
        )
        self.assertEqual(
            month_hours_sum(vehicle_rz=self.rz_a, year=2030, month=5),
            Decimal("3.75"),
        )

    def test_report_summary_top_by_hours(self):
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_a,
            repair_date=date(2030, 5, 1),
            hours=Decimal("3.00"),
            created_by=self.admin,
        )
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_b,
            repair_date=date(2030, 5, 2),
            hours=Decimal("5.00"),
            created_by=self.admin,
        )
        VehicleRzRepair.objects.create(
            vehicle_rz=self.rz_b,
            repair_date=date(2030, 5, 3),
            hours=Decimal("1.00"),
            created_by=self.admin,
        )
        summary = build_vehicle_repairs_summary(
            ReportDateRange(date_from=date(2030, 5, 1), date_to=date(2030, 5, 31))
        )
        self.assertEqual(summary.total_hours, Decimal("9.00"))
        self.assertEqual(summary.top_vehicle_rz, "2B22222")
        self.assertEqual(summary.top_vehicle_hours, Decimal("6.00"))

        ops = build_operations_summary(
            ReportDateRange(date_from=date(2030, 5, 1), date_to=date(2030, 5, 31))
        )
        labels = [k.label for k in ops.kpis]
        self.assertIn("Opravy — hodiny", labels)
        self.assertIn("Opravy — nejvíce opravované", labels)

    def test_repair_list_requires_admin(self):
        url = reverse("catalogs:vehicle_rz_repair_list", args=[self.profile_a.pk])
        self.client.force_login(self.admin)
        response = self.client.get(url, {"year": 2030, "month": 5})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Evidence oprav")
        self.assertContains(response, self.rz_a.value)
