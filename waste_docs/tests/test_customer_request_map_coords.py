"""Testy fallback řetězce souřadnic pro mapu detailu požadavku."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    WasteTypeCatalog,
)
from customer_requests.models import CustomerRequest
from waste_docs.services.customer_request_map_coords import resolve_customer_request_map_coords


class CustomerRequestMapCoordsTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("map_coords_user", password="pw")

        self.name = NameCatalog.objects.create(value="Subjekt coords")
        self.ico = IcoCatalog.objects.create(value="25257684")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)

        self.activity = ActivityCatalog.objects.create(name="Činnost coords")
        self.wt = WasteTypeCatalog.objects.create(code="200501", value="W coords")
        self.suf = SuffixCatalog.objects.create(value="KC")
        self.address = AddressCatalog.objects.create(value="Coords ulice, 1, Město")

    def _make_request(self, **kwargs):
        return CustomerRequest.objects.create(
            created_by=self.user,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2038, 5, 1),
            status=CustomerRequest.Status.DRAFT,
            **kwargs,
        )

    def _set_subject_coords(self, lat, lng):
        self.profile.fulfillment_latitude = lat
        self.profile.fulfillment_longitude = lng
        self.profile.address_profile.save()

    def test_own_coords_take_priority(self):
        own_lat = Decimal("50.0833333")
        own_lng = Decimal("14.4166667")
        self._set_subject_coords(Decimal("49.1111111"), Decimal("15.2222222"))
        item = self._make_request(fulfillment_latitude=own_lat, fulfillment_longitude=own_lng)

        lat, lng = resolve_customer_request_map_coords(item)
        self.assertEqual(lat, own_lat)
        self.assertEqual(lng, own_lng)

    def test_fallback_to_subject_coords(self):
        subj_lat = Decimal("50.4156486")
        subj_lng = Decimal("14.9326140")
        self._set_subject_coords(subj_lat, subj_lng)
        item = self._make_request()

        lat, lng = resolve_customer_request_map_coords(item)
        self.assertEqual(lat, subj_lat)
        self.assertEqual(lng, subj_lng)

    def test_no_coords_returns_none(self):
        item = self._make_request()

        lat, lng = resolve_customer_request_map_coords(item)
        self.assertIsNone(lat)
        self.assertIsNone(lng)
