"""Testy heuristiky optimalizace pořadí zastávek."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from core.services.ride_route_optimizer import format_route_order_output, optimize_route_order
from core.services.ride_route_reorder.route_optimizer import (
    ActivityKind,
    classify_activity,
    is_depot_stop,
    parse_time_constraints,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


class RouteOptimizerUnitTests(TestCase):
    def test_depot_detection(self):
        ride = Pruvodka(
            name_snapshot="COMPAG MLADÁ BOLESLAV s.r.o.",
            waste_type_snapshot="Nic",
            suffix_snapshot="Nic",
        )
        self.assertTrue(is_depot_stop(ride))

    def test_parse_hard_time(self):
        self.assertEqual(parse_time_constraints("v 9h"), (540, None))
        self.assertEqual(parse_time_constraints("kolem 12h")[1], 720)

    def test_classify_pristavit_a_stahnout(self):
        ride = Pruvodka(activity_snapshot="Přistavit a Stáhnout")
        self.assertEqual(classify_activity(ride), ActivityKind.PRISTAVIT_STAHNOUT)


class RouteOptimizerExampleTests(TestCase):
    """Příklad z dokumentace dispečinku."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("opt_admin", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)
        self.day = date(2026, 6, 16)
        self.rz = VehicleRzCatalog.objects.create(value="7P66666")
        ico = IcoCatalog.objects.create(value="12345678")
        waste_bio = WasteTypeCatalog.objects.create(code="880201", value="Biologicky rozložitelný odpad")
        waste_obj = WasteTypeCatalog.objects.create(code="880202", value="Objemný odpad")
        waste_pap = WasteTypeCatalog.objects.create(code="880203", value="Papírové a lepenkové obaly")
        waste_ul = WasteTypeCatalog.objects.create(code="880204", value="Uliční smetky")
        waste_nic = WasteTypeCatalog.objects.create(code="880205", value="Nic")
        wc = WasteCodeCatalog.objects.create(value="WCO")
        wcat = WasteCategoryCatalog.objects.create(value="KCO")
        common = {
            "ico": ico,
            "waste_code": wc,
            "waste_category": wcat,
            "drive_date": self.day,
            "created_by": self.admin,
            "vehicle_rz": self.rz,
            "vehicle_rz_snapshot": "7P66666",
        }

        name_cache: dict[str, NameCatalog] = {}
        address_cache: dict[str, AddressCatalog] = {}

        def mk(name, activity, address, waste, suffix, note=""):
            if name not in name_cache:
                name_cache[name] = NameCatalog.objects.create(value=name)
            n = name_cache[name]
            if address not in address_cache:
                address_cache[address] = AddressCatalog.objects.create(value=address)
            a = address_cache[address]
            return Pruvodka.objects.create(
                **common,
                name=n,
                address=a,
                waste_type=waste,
                name_snapshot=name,
                address_snapshot=address,
                activity_snapshot=activity,
                waste_type_snapshot=waste.value,
                suffix_snapshot=suffix,
                contact_note=note,
            )

        self.r813 = mk(
            "COMPAG MLADÁ BOLESLAV s.r.o.",
            "Nic",
            "Depo",
            waste_nic,
            "Nic",
        )
        self.r788 = mk(
            "Střední škola, ZŠ, MŠ, Dětský domov a SPC Mladá Boleslav",
            "Přistavit",
            "Na Celně 915/2, Mladá Boleslav",
            waste_obj,
            "—",
            "vysoký kontejner, vjezd do dvora z křižovatky",
        )
        self.r791 = mk(
            "Francová Ivana",
            "Přistavit a Stáhnout",
            "Dolní Bousov 69",
            waste_bio,
            "Chrást Kompostárna Compag",
            "v 9h",
        )
        self.r790 = mk(
            "KiK textil a Non-Food spol. s r.o.",
            "Výměna vlastní",
            "Jičínská 1418, Mladá Boleslav",
            waste_pap,
            "Roin COMPAG",
            "ručaři Marina",
        )
        addr_mb = "Komenského náměstí 61, Mladá Boleslav"
        self.r806 = mk(
            "Statutární město Mladá Boleslav",
            "Jiná činnost",
            addr_mb,
            waste_ul,
            "Michalovická skládka",
        )
        self.r807 = mk(
            "Statutární město Mladá Boleslav",
            "Jiná činnost",
            addr_mb,
            waste_ul,
            "Michalovická skládka",
        )
        self.items = [self.r813, self.r788, self.r791, self.r790, self.r806, self.r807]

    def test_example_route_order(self):
        order = optimize_route_order(self.items)
        self.assertEqual(
            order,
            [self.r813.pk, self.r788.pk, self.r791.pk, self.r790.pk, self.r806.pk, self.r807.pk],
        )

    def test_output_format_pk_only(self):
        order = optimize_route_order(self.items)
        output = format_route_order_output(order)
        lines = output.strip().split("\n")
        self.assertEqual(len(lines), 6)
        self.assertTrue(all(line.isdigit() for line in lines))

    def test_optimize_api(self):
        self.client.force_login(self.admin)
        from core.services.ride_grouping import ride_group_key

        Pruvodka.objects.filter(pk=self.r813.pk).update(
            ride_group_number=100,
            ride_sequence=1,
            driver_snapshot="Test",
        )
        for seq, ride in enumerate(self.items[1:], start=2):
            Pruvodka.objects.filter(pk=ride.pk).update(
                ride_group_number=100,
                ride_sequence=seq,
                driver_snapshot="Test",
            )
        key = ride_group_key(self.day, self.rz.pk, None)
        url = reverse("core:ride_group_optimize")
        resp = self.client.get(url + f"?date={self.day.isoformat()}&ride_group={key}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["order"]), 6)
