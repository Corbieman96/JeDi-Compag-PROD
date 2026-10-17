from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

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
from waste_docs.services.pruvodka_generated_files import regenerate_all_excels
from waste_docs.services.ride_bulk_actions import rides_for_day
from waste_docs.services.ride_print_order import sort_rides_list
from waste_docs.services.ride_protocol_xlsx import rides_for_protocol_day


class RidePrintOrderTests(TestCase):
    def test_sort_rides_list_uses_ride_sequence_not_created_at(self):
        later = Pruvodka(
            pk=2,
            vehicle_rz_snapshot="1P11111",
            driver_snapshot="Jan Novák",
            ride_group_number=100,
            ride_sequence=2,
            snd_cislo_listu="0000100-2026-2",
        )
        earlier = Pruvodka(
            pk=1,
            vehicle_rz_snapshot="1P11111",
            driver_snapshot="Jan Novák",
            ride_group_number=100,
            ride_sequence=1,
            snd_cislo_listu="0000100-2026-1",
        )
        ordered = sort_rides_list([later, earlier])
        self.assertEqual([ride.pk for ride in ordered], [1, 2])

    def test_sort_rides_list_orders_rz_then_driver(self):
        ride_b = Pruvodka(
            pk=2,
            vehicle_rz_snapshot="2P22222",
            driver_snapshot="Adam Svoboda",
            ride_group_number=200,
            ride_sequence=1,
        )
        ride_a = Pruvodka(
            pk=1,
            vehicle_rz_snapshot="1P11111",
            driver_snapshot="Zdeněk Malý",
            ride_group_number=100,
            ride_sequence=1,
        )
        ordered = sort_rides_list([ride_b, ride_a])
        self.assertEqual([ride.pk for ride in ordered], [1, 2])


class RidePrintOrderIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("order_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.ride_date = date(2026, 6, 8)
        self.rz_a = VehicleRzCatalog.objects.create(value="1P11111")
        self.rz_b = VehicleRzCatalog.objects.create(value="2P22222")
        name = NameCatalog.objects.create(value="Subjekt order test")
        ico = IcoCatalog.objects.create(value="11223344")
        address = AddressCatalog.objects.create(value="Adr order")
        waste_type = WasteTypeCatalog.objects.create(code="880088", value="Worder")
        waste_code = WasteCodeCatalog.objects.create(value="WCOR")
        waste_category = WasteCategoryCatalog.objects.create(value="KOOR")
        suffix = SuffixCatalog.objects.create(value="SFXOR")
        common = dict(
            name=name,
            ico=ico,
            address=address,
            waste_type=waste_type,
            waste_code=waste_code,
            waste_category=waste_category,
            suffix=suffix,
            drive_date=self.ride_date,
            created_by=self.admin,
            container_number="",
        )
        self.ride_first = Pruvodka.objects.create(
            vehicle_rz=self.rz_a,
            vehicle_rz_snapshot="1P11111",
            driver_snapshot="Jan Novák",
            ride_group_number=100,
            ride_sequence=1,
            snd_cislo_listu="0000100-2026-1",
            created_at=datetime(2026, 6, 8, 14, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_second = Pruvodka.objects.create(
            vehicle_rz=self.rz_a,
            vehicle_rz_snapshot="1P11111",
            driver_snapshot="Jan Novák",
            ride_group_number=100,
            ride_sequence=2,
            snd_cislo_listu="0000100-2026-2",
            created_at=datetime(2026, 6, 8, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.ride_other_rz = Pruvodka.objects.create(
            vehicle_rz=self.rz_b,
            vehicle_rz_snapshot="2P22222",
            driver_snapshot="Adam Svoboda",
            ride_group_number=200,
            ride_sequence=1,
            snd_cislo_listu="0000200-2026",
            created_at=datetime(2026, 6, 8, 8, 0, tzinfo=dt_timezone.utc),
            **common,
        )

    def test_rides_for_day_and_protocol_day_share_order(self):
        day_pks = [ride.pk for ride in rides_for_day(self.ride_date, self.admin)]
        protocol_pks = [ride.pk for ride in rides_for_protocol_day(self.ride_date, self.admin)]
        self.assertEqual(day_pks, protocol_pks)
        self.assertEqual(
            day_pks,
            [self.ride_first.pk, self.ride_second.pk, self.ride_other_rz.pk],
        )

    @patch("waste_docs.services.pruvodka_generated_files.apply_pruvodka_status_after_save")
    @patch("waste_docs.services.pruvodka_generated_files.generate_xlsx")
    @patch("waste_docs.services.pruvodka_generated_files.should_generate_excel", return_value=True)
    def test_regenerate_all_excels_processes_sorted_rides(
        self,
        _mock_should,
        mock_generate,
        _mock_status,
    ):
        mock_generate.return_value = str(settings.MEDIA_ROOT / "pruvodky" / "fake.xlsx")
        rides = [self.ride_second, self.ride_other_rz, self.ride_first]
        regenerate_all_excels(rides)
        processed_pks = [call.args[0].pk for call in mock_generate.call_args_list]
        self.assertEqual(
            processed_pks,
            [self.ride_first.pk, self.ride_second.pk, self.ride_other_rz.pk],
        )
