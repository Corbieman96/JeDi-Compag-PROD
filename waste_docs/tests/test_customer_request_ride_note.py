"""Poznámka požadavku, která se propíše do jízdy (contact_note → pár → note)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    WasteTypeCatalog,
)
from customer_requests.models import CustomerRequest
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.services.customer_request_ride_note import ride_note_for_customer_request


class RideNoteHelperTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="Subjekt note")
        self.activity = ActivityCatalog.objects.create(name="Činnost note")
        self.wt = WasteTypeCatalog.objects.create(code="200377", value="W note")
        self.suf = SuffixCatalog.objects.create(value="S note")
        self.address = AddressCatalog.objects.create(value="Adr note")
        User = get_user_model()
        self.user = User.objects.create_user("ride_note_u", password="pw")

    def _cr(self, *, contact_note: str, note: str) -> CustomerRequest:
        return CustomerRequest.objects.create(
            created_by=self.user,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2026, 8, 10),
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
            contact_note=contact_note,
            note=note,
        )

    def test_contact_note_has_priority(self):
        cr = self._cr(contact_note="Kontakt", note="Pozadavek")
        self.assertEqual(ride_note_for_customer_request(cr), "Kontakt")

    def test_fallback_to_note(self):
        cr = self._cr(contact_note="", note="Pozadavek")
        self.assertEqual(ride_note_for_customer_request(cr), "Pozadavek")

    def test_empty_when_both_blank(self):
        cr = self._cr(contact_note="", note="")
        self.assertEqual(ride_note_for_customer_request(cr), "")

    def test_fallback_to_pair_yard_note(self):
        ico = IcoCatalog.objects.create(value="99112233")
        subject = NameSubjectProfile.objects.create(name=self.name, ico=ico)
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_dispatch_note_text="v 8 hod, vysoký",
        )
        cr = self._cr(contact_note="", note="")
        self.assertEqual(ride_note_for_customer_request(cr), "v 8 hod, vysoký")

    def test_pair_note_beats_general_note(self):
        ico = IcoCatalog.objects.create(value="99112236")
        subject = NameSubjectProfile.objects.create(name=self.name, ico=ico)
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_dispatch_note_text="v 8 hod, vysoký, výměna",
        )
        cr = self._cr(contact_note="", note="stažená - dopoledne")
        self.assertEqual(ride_note_for_customer_request(cr), "v 8 hod, vysoký, výměna")

    def test_contact_note_beats_pair_note(self):
        ico = IcoCatalog.objects.create(value="99112234")
        subject = NameSubjectProfile.objects.create(name=self.name, ico=ico)
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject,
            waste_type=self.wt,
            suffix=self.suf,
            ride_note="z paru",
        )
        cr = self._cr(contact_note="z CR", note="")
        self.assertEqual(ride_note_for_customer_request(cr), "z CR")


class RideNoteDetailViewTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("ride_note_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)

        self.name = NameCatalog.objects.create(value="Subjekt note view")
        self.activity = ActivityCatalog.objects.create(name="Činnost note view")
        self.wt = WasteTypeCatalog.objects.create(code="200378", value="W note view")
        self.suf = SuffixCatalog.objects.create(value="S note view")
        self.address = AddressCatalog.objects.create(value="Adr note view")

    def _detail(self, cr: CustomerRequest):
        client = Client()
        client.force_login(self.dispecer)
        return client.get(reverse("waste_docs:customer_request_detail", kwargs={"pk": cr.pk}))

    def test_detail_shows_contact_note_as_ride_note(self):
        cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2026, 8, 11),
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
            contact_note="Kontaktni pozn do jizdy",
            note="Jina pozn pozadavku",
        )
        response = self._detail(cr)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Poznámka do jízdy:")
        self.assertContains(response, "Kontaktni pozn do jizdy")
        self.assertContains(response, "Poznámka požadavku:")
        self.assertContains(response, "Jina pozn pozadavku")

    def test_detail_ride_note_falls_back_to_note(self):
        cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2026, 8, 12),
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
            contact_note="",
            note="Jen pozadavek",
        )
        response = self._detail(cr)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Poznámka do jízdy:")
        self.assertContains(response, "Jen pozadavek")
        self.assertNotContains(response, "Poznámka požadavku:")

    def test_detail_shows_pair_note_near_ride_counts(self):
        ico = IcoCatalog.objects.create(value="99112235")
        subject = NameSubjectProfile.objects.create(name=self.name, ico=ico)
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_dispatch_note_text="v 8 hod, vysoký, výměna",
        )
        cr = CustomerRequest.objects.create(
            created_by=self.dispecer,
            name=self.name,
            activity=self.activity,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=date(2026, 8, 13),
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
            contact_note="",
            note="",
        )
        response = self._detail(cr)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Poznámka do jízdy:")
        self.assertContains(response, "Poznámka (odpad):")
        self.assertContains(response, "v 8 hod, vysoký, výměna")
