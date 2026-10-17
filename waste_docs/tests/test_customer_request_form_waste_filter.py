from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

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
from catalogs.models.vehicle_rz import VehicleKindCatalog
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm
from waste_docs.services.customer_request_form.subject_snapshot import (
    subject_snapshot_for_customer_request_form,
)


class CustomerRequestFormWasteFilterTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("cr_wf_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2038, 8, 1)

        self.name = NameCatalog.objects.create(value="Subjekt filtr odpadů")
        self.ico = IcoCatalog.objects.create(value="11223344")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Filtr ulice 1, Město")

        self.wt_allowed_1 = WasteTypeCatalog.objects.create(code="200401", value="Povolený A")
        self.wt_allowed_2 = WasteTypeCatalog.objects.create(code="200402", value="Povolený B")
        self.wt_other = WasteTypeCatalog.objects.create(code="200499", value="Nepovolený X")
        self.suf_a = SuffixCatalog.objects.create(value="FA")
        self.suf_b = SuffixCatalog.objects.create(value="FB")
        self.vk = VehicleKindCatalog.objects.create(name="Hák filtr", shortcut="Hf", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz filtr", visible_for_submitter=True)

        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt_allowed_1,
            suffix=self.suf_a,
            yard_vehicle_kind=self.vk,
            contract_number="SML-FILTR-1",
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt_allowed_2,
            suffix=self.suf_b,
            yard_vehicle_kind=self.vk,
        )

        self.cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt_allowed_1,
            suffix=self.suf_a,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.RETURNED_FOR_FIX,
        )

    def test_subject_snapshot_returns_only_profile_waste_ids(self):
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        self.assertIsNotNone(snapshot)
        allowed = set(snapshot["allowed_waste_type_ids"])
        self.assertEqual(allowed, {self.wt_allowed_1.pk, self.wt_allowed_2.pk})
        self.assertNotIn(self.wt_other.pk, allowed)

    def test_form_waste_type_queryset_limited_to_subject(self):
        form = CustomerRequestForm(instance=self.cr, submit_user=self.zadavatel)
        qs_ids = set(form.fields["waste_type"].queryset.values_list("pk", flat=True))
        self.assertEqual(qs_ids, {self.wt_allowed_1.pk, self.wt_allowed_2.pk})
        self.assertNotIn(self.wt_other.pk, qs_ids)

    def test_fix_edit_get_includes_initial_subject_snapshot(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "customer-request-form-config")
        marker = 'id="customer-request-form-config"'
        start = response.content.decode().index(marker)
        json_start = response.content.decode().index(">", start) + 1
        json_end = response.content.decode().index("</script>", json_start)
        config = json.loads(response.content.decode()[json_start:json_end])
        snapshot = config.get("initialSubjectSnapshot")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["name_id"], self.name.pk)
        self.assertEqual(
            set(snapshot["allowed_waste_type_ids"]),
            {self.wt_allowed_1.pk, self.wt_allowed_2.pk},
        )

    def test_subject_snapshot_includes_fulfillment_coords(self):
        addr_profile = self.profile._address()
        addr_profile.fulfillment_latitude = Decimal("50.1111111")
        addr_profile.fulfillment_longitude = Decimal("15.2222222")
        addr_profile.save()
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        self.assertEqual(snapshot["fulfillment_latitude"], "50.1111111")
        self.assertEqual(snapshot["fulfillment_longitude"], "15.2222222")

    def test_fix_edit_bootstraps_fulfillment_coords_on_load(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrapCoordsFromAddress")
        self.assertContains(response, "fulfillmentAddressFieldConfig")

    def test_subject_snapshot_pair_hints_include_contract_number(self):
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        hints = snapshot["pair_hints"]
        match = next(h for h in hints if h["waste_type_id"] == self.wt_allowed_1.pk)
        self.assertEqual(match["contract_number"], "SML-FILTR-1")

    def test_subject_snapshot_pair_hints_own_fulfillment_address(self):
        pair_addr = AddressCatalog.objects.create(value="Sklad filtr, 9, Město")
        pair = NameSubjectWasteSuffixPair.objects.get(
            subject_profile=self.profile,
            waste_type=self.wt_allowed_1,
        )
        pair.fulfillment_address = pair_addr
        pair.save(update_fields=["fulfillment_address"])
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        with_own = next(h for h in snapshot["pair_hints"] if h["waste_type_id"] == self.wt_allowed_1.pk)
        without = next(h for h in snapshot["pair_hints"] if h["waste_type_id"] == self.wt_allowed_2.pk)
        self.assertEqual(with_own["own_fulfillment_address_value"], pair_addr.value)
        self.assertEqual(with_own["fulfillment_address_value"], pair_addr.value)
        self.assertEqual(without["own_fulfillment_address_value"], "")

    def test_form_initial_contract_number_from_pair_on_edit(self):
        form = CustomerRequestForm(instance=self.cr, submit_user=self.zadavatel)
        self.assertEqual(form.initial.get("contract_number"), "SML-FILTR-1")

    def test_create_and_edit_include_contract_sync_script(self):
        client = Client()
        client.force_login(self.zadavatel)
        for url_name, args in (
            ("waste_docs:customer_request_create", None),
            ("waste_docs:customer_request_form_edit", [self.cr.pk]),
        ):
            url = reverse(url_name, args=args) if args else reverse(url_name)
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "customer-request-contract-row")
            self.assertContains(response, "syncContractFromPair")
            self.assertContains(response, "syncFulfillmentFromPair")
            self.assertContains(response, "syncActivityFromPair")
            self.assertContains(response, "preferPairHintForActivity")
            self.assertContains(response, "pairHintCandidates")
            self.assertContains(response, "own_fulfillment_address_value")
            self.assertContains(response, "customer-request-pair-address-select")
            self.assertContains(response, "buildPairAddressOptions")
            self.assertContains(response, "preferPairHint")

    def test_subject_snapshot_pair_hints_include_activity_from_svoz(self):
        pair = NameSubjectWasteSuffixPair.objects.get(
            subject_profile=self.profile,
            waste_type=self.wt_allowed_1,
        )
        pair.yard_svoz_activity = self.activity
        pair.save(update_fields=["yard_svoz_activity"])
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        match = next(h for h in snapshot["pair_hints"] if h["waste_type_id"] == self.wt_allowed_1.pk)
        self.assertEqual(match["activity_id"], self.activity.pk)

    def test_subject_snapshot_pair_hints_prefer_pruvodka_activity(self):
        pruvodka_act = ActivityCatalog.objects.create(name="Průvodka filtr", visible_for_submitter=True)
        pair = NameSubjectWasteSuffixPair.objects.get(
            subject_profile=self.profile,
            waste_type=self.wt_allowed_2,
        )
        pair.yard_svoz_activity = self.activity
        pair.yard_pruvodka_activity = pruvodka_act
        pair.save(update_fields=["yard_svoz_activity", "yard_pruvodka_activity"])
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        match = next(h for h in snapshot["pair_hints"] if h["waste_type_id"] == self.wt_allowed_2.pk)
        self.assertEqual(match["activity_id"], pruvodka_act.pk)

    def test_subject_snapshot_pair_hints_without_activity(self):
        snapshot = subject_snapshot_for_customer_request_form(name_id=self.name.pk)
        for hint in snapshot["pair_hints"]:
            self.assertIsNone(hint.get("activity_id"))
