from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.ride_bulk_actions import rides_for_print_scope


class MergedPrintScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("merge_scope_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.ride_date = date(2026, 6, 9)
        self.rz_a = VehicleRzCatalog.objects.create(value="1P11111")
        self.rz_b = VehicleRzCatalog.objects.create(value="2P22222")
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt merge scope"),
            ico=IcoCatalog.objects.create(value="11223355"),
            address=AddressCatalog.objects.create(value="Adr merge"),
            waste_type=WasteTypeCatalog.objects.create(code="880099", value="Wmerge"),
            waste_code=WasteCodeCatalog.objects.create(value="WCMG"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOMG"),
            suffix=SuffixCatalog.objects.create(value="SFXMG"),
            drive_date=self.ride_date,
            created_by=self.admin,
            container_number="",
        )
        self.ride_a1 = Pruvodka.objects.create(
            vehicle_rz=self.rz_a,
            vehicle_rz_snapshot="1P11111",
            ride_group_number=100,
            ride_sequence=1,
            created_at=datetime(2026, 6, 9, 10, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_b1 = Pruvodka.objects.create(
            vehicle_rz=self.rz_b,
            vehicle_rz_snapshot="2P22222",
            ride_group_number=200,
            ride_sequence=1,
            created_at=datetime(2026, 6, 9, 11, 0, tzinfo=dt_timezone.utc),
            **common,
        )

    def test_rides_for_print_scope_filters_vehicle_rz(self):
        scoped = rides_for_print_scope(
            self.ride_date,
            self.admin,
            vehicle_rz_id=self.rz_a.pk,
        )
        self.assertEqual([ride.pk for ride in scoped], [self.ride_a1.pk])

    def test_rides_for_print_scope_all_when_vehicle_rz_zero(self):
        scoped = rides_for_print_scope(self.ride_date, self.admin, vehicle_rz_id=0)
        self.assertEqual(
            sorted(ride.pk for ride in scoped),
            sorted([self.ride_a1.pk, self.ride_b1.pk]),
        )

    def test_rides_for_print_scope_respects_pks(self):
        scoped = rides_for_print_scope(
            self.ride_date,
            self.admin,
            vehicle_rz_id=self.rz_a.pk,
            filter_pks=[self.ride_a1.pk],
        )
        self.assertEqual([ride.pk for ride in scoped], [self.ride_a1.pk])


class ReportsIndexViewTests(TestCase):
    def test_reports_index_renders_for_superuser(self):
        User = get_user_model()
        admin = User.objects.create_user("reports_index_admin", password="pw", is_superuser=True)
        client = Client()
        client.force_login(admin)
        response = client.get(reverse("reports:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reporty")
