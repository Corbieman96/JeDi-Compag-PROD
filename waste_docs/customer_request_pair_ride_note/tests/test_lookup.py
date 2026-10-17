"""Lookup ride_note páru pro formulář požadavku (H3 vs M16)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.customer_request_pair_ride_note.services.lookup import lookup_pair_ride_note

H3_ADDR = "třída Václava Klementa, H3, Mladá Boleslav"
M16_ADDR = "třída Václava Klementa, M16, Mladá Boleslav"
H3_NOTE = "stř. 2251. Tel: 605 293 708 Lánský"


class PairRideNoteLookupTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Škoda Auto a.s. lookup")
        self.ico = IcoCatalog.objects.create(value="00177041")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.wt = WasteTypeCatalog.objects.create(code="200307", value="Objemný odpad lookup")
        self.suf = SuffixCatalog.objects.create(value="Překladiště lookup")
        self.addr_m16 = AddressCatalog.objects.create(value=M16_ADDR)
        self.addr_h3 = AddressCatalog.objects.create(value=H3_ADDR)
        self.pair_m16 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=self.addr_m16,
            ride_note="",
            sort_order=1,
        )
        self.pair_h3 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=self.addr_h3,
            ride_note=H3_NOTE,
            sort_order=2,
        )

    def test_pair_id_returns_h3_note(self):
        self.assertEqual(
            lookup_pair_ride_note(pair_id=self.pair_h3.pk),
            H3_NOTE,
        )

    def test_pair_id_m16_empty_falls_back_to_address_h3(self):
        self.assertEqual(
            lookup_pair_ride_note(
                pair_id=self.pair_m16.pk,
                name_id=self.name.pk,
                waste_type_id=self.wt.pk,
                suffix_id=self.suf.pk,
                address=H3_ADDR,
            ),
            H3_NOTE,
        )

    def test_address_h3_returns_note_not_first_m16(self):
        self.assertEqual(
            lookup_pair_ride_note(
                name_id=self.name.pk,
                waste_type_id=self.wt.pk,
                suffix_id=self.suf.pk,
                address=H3_ADDR,
            ),
            H3_NOTE,
        )

    def test_address_m16_returns_empty(self):
        self.assertEqual(
            lookup_pair_ride_note(
                name_id=self.name.pk,
                waste_type_id=self.wt.pk,
                suffix_id=self.suf.pk,
                address=M16_ADDR,
            ),
            "",
        )

    def test_address_match_ignores_extra_whitespace(self):
        self.assertEqual(
            lookup_pair_ride_note(
                name_id=self.name.pk,
                waste_type_id=self.wt.pk,
                address="  třída Václava Klementa,   H3,  Mladá Boleslav ",
            ),
            H3_NOTE,
        )


class PairRideNoteAjaxViewTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("pair_note_ajax", password="pw")
        set_user_role(self.user, ROLE_ZADAVATEL)
        self.name = NameCatalog.objects.create(value="Škoda Auto ajax")
        self.ico = IcoCatalog.objects.create(value="00177042")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.wt = WasteTypeCatalog.objects.create(code="200308", value="Objemný ajax")
        self.suf = SuffixCatalog.objects.create(value="Překladiště ajax")
        self.addr_m16 = AddressCatalog.objects.create(value=M16_ADDR)
        self.addr_h3 = AddressCatalog.objects.create(value=H3_ADDR)
        self.pair_m16 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=self.addr_m16,
            ride_note="",
            sort_order=1,
        )
        self.pair_h3 = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            fulfillment_address=self.addr_h3,
            ride_note=H3_NOTE,
            sort_order=2,
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.url = reverse("waste_docs:customer_request_pair_ride_note")

    def test_get_by_pair_id(self):
        res = self.client.get(self.url, {"pair_id": self.pair_h3.pk})
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ride_note"], H3_NOTE)

    def test_get_by_address(self):
        res = self.client.get(
            self.url,
            {
                "name_id": self.name.pk,
                "waste_type_id": self.wt.pk,
                "suffix_id": self.suf.pk,
                "address": H3_ADDR,
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["ride_note"], H3_NOTE)

    def test_get_m16_empty(self):
        res = self.client.get(
            self.url,
            {
                "pair_id": self.pair_m16.pk,
                "name_id": self.name.pk,
                "waste_type_id": self.wt.pk,
                "address": M16_ADDR,
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["ride_note"], "")

    def test_create_form_includes_ajax_url(self):
        page = self.client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "/waste-docs/customer-requests/pair-ride-note/")
        self.assertContains(page, "requestRideNoteFromServer")
