from __future__ import annotations

from datetime import date

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
from waste_docs.models import Pruvodka
from waste_docs.pruvodka_search import filter_pruvodka_queryset_by_search


class PruvodkaSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("pruv_search", password="pw", is_superuser=True)
        name = NameCatalog.objects.create(value="Bělohubý s.r.o.")
        self.ride = Pruvodka.objects.create(
            name=name,
            name_snapshot="Bělohubý s.r.o.",
            ico=IcoCatalog.objects.create(value="12345678"),
            ico_snapshot="12345678",
            address=AddressCatalog.objects.create(value="Adresa test"),
            address_snapshot="Adresa test",
            waste_type=WasteTypeCatalog.objects.create(code="990099", value="Wsearch"),
            waste_code=WasteCodeCatalog.objects.create(value="WCSEARCH"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCSEARCH"),
            suffix=SuffixCatalog.objects.create(value="SSEARCH"),
            vehicle_rz=VehicleRzCatalog.objects.create(value="1A11111"),
            vehicle_rz_snapshot="1A11111",
            drive_date=date(2026, 6, 12),
            container_number="",
            created_by=self.user,
        )
        self.base_qs = Pruvodka.objects.filter(is_archived=False)

    def _search(self, query: str):
        return filter_pruvodka_queryset_by_search(self.base_qs, query)

    def test_empty_query_returns_all(self):
        self.assertEqual(self._search("").count(), 1)
        self.assertEqual(self._search("   ").count(), 1)

    def test_case_insensitive_czech_name(self):
        for query in ("bělohubý", "BĚLOHUBÝ", "Bělohubý", "belohuby"):
            with self.subTest(query=query):
                qs = self._search(query)
                self.assertEqual(list(qs.values_list("pk", flat=True)), [self.ride.pk])

    def test_and_between_terms(self):
        qs = self._search("Bělohubý 1A11111")
        self.assertEqual(list(qs.values_list("pk", flat=True)), [self.ride.pk])

    def test_no_match_returns_empty(self):
        self.assertFalse(self._search("neexistující subjekt").exists())

    def test_pk_digit_search(self):
        qs = self._search(str(self.ride.pk))
        self.assertEqual(list(qs.values_list("pk", flat=True)), [self.ride.pk])

    def test_spaced_letters_in_name_match_compact_query(self):
        spaced = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="S U M O s.r.o"),
            name_snapshot="S U M O s.r.o",
            ico=IcoCatalog.objects.create(value="87654321"),
            ico_snapshot="87654321",
            address=AddressCatalog.objects.create(value="Adresa SUMO"),
            address_snapshot="Adresa SUMO",
            waste_type=self.ride.waste_type,
            waste_code=self.ride.waste_code,
            waste_category=self.ride.waste_category,
            suffix=self.ride.suffix,
            vehicle_rz=self.ride.vehicle_rz,
            vehicle_rz_snapshot=self.ride.vehicle_rz_snapshot,
            drive_date=date(2026, 6, 13),
            container_number="",
            created_by=self.user,
        )
        qs = filter_pruvodka_queryset_by_search(
            Pruvodka.objects.filter(is_archived=False),
            "SUMO",
        )
        self.assertIn(spaced.pk, list(qs.values_list("pk", flat=True)))
