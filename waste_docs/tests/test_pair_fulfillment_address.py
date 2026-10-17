"""Adresa plnění na řádku F/P — resolver a uložení formuláře."""

from django.test import TestCase

from catalogs.forms.name_subject_pairs import NameSubjectWasteSuffixPairForm
from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from catalogs.services.pair_fulfillment_address import (
    central_fulfillment_address_value,
    fulfillment_address_for_pruvodka_context,
    fulfillment_address_value_for_pair,
    known_fulfillment_addresses_for_form,
    known_fulfillment_addresses_for_subject,
    resolved_central_fulfillment_address,
)
from catalogs.forms import NameSubjectProfileForm


class PairFulfillmentAddressResolverTests(TestCase):
    def setUp(self):
        self.profile = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Subj adresa"),
            company_name="Subj adresa",
        )
        self.central_addr = AddressCatalog.objects.create(value="Centrální, 1, Město")
        self.pair_addr = AddressCatalog.objects.create(value="Pár ulice, 2, Město")
        ap = self.profile.address_profile
        ap.fulfillment_address = self.central_addr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="Odpad A")
        self.wt2 = WasteTypeCatalog.objects.create(code="200302", value="Odpad B")
        self.suffix = SuffixCatalog.objects.create(value="K1")
        self.suffix2 = SuffixCatalog.objects.create(value="K2")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")
        self.vk_3h = VehicleKindCatalog.objects.create(name="3H", shortcut="3H")
        self.activity = ActivityCatalog.objects.create(name="Svoz")

        self.pair_dup_kind_h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suffix,
            fulfillment_address=self.pair_addr,
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_vehicle_kind=self.vk_h,
        )
        self.pair_dup_kind_h.yard_vehicle_kinds.add(self.vk_h)

        self.pair_dup_kind_3h = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suffix,
            fulfillment_address=AddressCatalog.objects.create(value="Jiná adresa, 3, Město"),
            yard_svoz_enabled=True,
            yard_svoz_activity=self.activity,
            yard_vehicle_kind=self.vk_3h,
        )
        self.pair_dup_kind_3h.yard_vehicle_kinds.add(self.vk_3h)

        self.pair_with_addr = self.pair_dup_kind_h
        self.pair_other_kind = self.pair_dup_kind_3h

        self.rz_h = VehicleRzCatalog.objects.create(value="1H11111")
        prof_h = VehicleRzProfile.objects.create(rz=self.rz_h)
        prof_h.vehicle_kinds.add(self.vk_h)

    def test_central_fallback_when_pair_empty(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt2,
            suffix=self.suffix,
        )
        self.assertEqual(central_fulfillment_address_value(self.profile), self.central_addr.value)
        self.assertEqual(
            fulfillment_address_value_for_pair(pair, self.profile),
            self.central_addr.value,
        )

    def test_pair_override_beats_central(self):
        self.assertEqual(
            fulfillment_address_value_for_pair(self.pair_with_addr, self.profile),
            self.pair_addr.value,
        )

    def test_context_resolves_by_vehicle_rz_kind(self):
        resolved_h = fulfillment_address_for_pruvodka_context(
            subject_profile=self.profile,
            waste_type_id=self.wt.pk,
            suffix_id=self.suffix.pk,
            vehicle_rz=self.rz_h,
        )
        self.assertEqual(resolved_h, self.pair_addr.value)

        rz_3h = VehicleRzCatalog.objects.create(value="1H33333")
        prof_3h = VehicleRzProfile.objects.create(rz=rz_3h)
        prof_3h.vehicle_kinds.add(self.vk_3h)
        resolved_3h = fulfillment_address_for_pruvodka_context(
            subject_profile=self.profile,
            waste_type_id=self.wt.pk,
            suffix_id=self.suffix.pk,
            vehicle_rz=rz_3h,
        )
        self.assertEqual(resolved_3h, self.pair_other_kind.fulfillment_address.value)

    def test_known_fulfillment_addresses_for_subject(self):
        other_addr = AddressCatalog.objects.create(value="Skladová, 7, Město")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt2,
            suffix=self.suffix2,
            fulfillment_address=other_addr,
        )
        known = known_fulfillment_addresses_for_subject(self.profile)
        self.assertEqual(known[0], self.central_addr.value)
        self.assertIn(other_addr.value, known)
        self.assertGreaterEqual(len(known), 2)

    def test_resolved_central_from_profile_form_initial(self):
        form = NameSubjectProfileForm(instance=self.profile, actor_user=None)
        self.assertEqual(
            resolved_central_fulfillment_address(form=form, profile=self.profile),
            self.central_addr.value,
        )

    def test_resolved_central_prefers_post_over_profile(self):
        form = NameSubjectProfileForm(
            {"fulfillment_address_value": "Nová ulice, 9, Město"},
            instance=self.profile,
            actor_user=None,
        )
        self.assertEqual(
            resolved_central_fulfillment_address(form=form, profile=self.profile),
            "Nová ulice, 9, Město",
        )
        known = known_fulfillment_addresses_for_form(form=form, profile=self.profile)
        self.assertEqual(known[0], "Nová ulice, 9, Město")

    def test_form_save_persists_pair_fulfillment_address(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt2,
            suffix=self.suffix2,
        )
        form = NameSubjectWasteSuffixPairForm(
            data={
                "waste_type": str(self.wt2.pk),
                "suffix": str(self.suffix2.pk),
                "fulfillment_address_value": "Nová adresa, 9, Vesnice",
            },
            instance=pair,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertIsNotNone(saved.fulfillment_address_id)
        self.assertEqual(saved.fulfillment_address.value, "Nová adresa, 9, Vesnice")

    def test_form_save_clears_pair_fulfillment_address(self):
        form = NameSubjectWasteSuffixPairForm(
            data={
                "waste_type": str(self.wt.pk),
                "suffix": str(self.suffix.pk),
                "fulfillment_address_value": "",
            },
            instance=self.pair_with_addr,
            subject_profile=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertIsNone(saved.fulfillment_address_id)
        self.assertEqual(
            fulfillment_address_value_for_pair(saved, self.profile),
            self.central_addr.value,
        )

    def test_form_save_matching_central_address_stores_null_override(self):
        form = NameSubjectWasteSuffixPairForm(
            data={
                "waste_type": str(self.wt.pk),
                "suffix": str(self.suffix.pk),
                "fulfillment_address_value": self.central_addr.value,
            },
            instance=self.pair_with_addr,
            subject_profile=self.profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get("fulfillment_address_value"), "")
        saved = form.save()
        saved.refresh_from_db()
        self.assertIsNone(saved.fulfillment_address_id)


class YardStandalonePairHintsPayloadTests(TestCase):
    def setUp(self):
        self.profile = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Yard subj"),
            company_name="Yard subj",
        )
        self.profile.yard_settings.is_collection_yard = True
        self.profile.yard_settings.save()
        self.central_addr = AddressCatalog.objects.create(value="Centrální dvůr, 1, Město")
        ap = self.profile.address_profile
        ap.fulfillment_address = self.central_addr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200399", value="Yard odpad")
        self.suffix = SuffixCatalog.objects.create(value="YD")
        self.vk = VehicleKindCatalog.objects.create(name="Hák yard", shortcut="HY")
        self.activity = ActivityCatalog.objects.create(name="Yard průvodka")
        self.pair_addr = AddressCatalog.objects.create(value="Sklad yard, 5, Město")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suffix,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
            fulfillment_address=self.pair_addr,
        )
        self.pair.yard_vehicle_kinds.add(self.vk)

    def test_yard_standalone_pair_hints_include_fulfillment_address(self):
        from waste_docs.services.yard_form_activity import yard_standalone_pair_hints_payload
        from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs

        pairs = list(
            yard_new_date_matrix_ready_qs(self.profile)
            .select_related("fulfillment_address", "yard_vehicle_kind")
            .prefetch_related("yard_vehicle_kinds")
        )
        hints = yard_standalone_pair_hints_payload(self.profile, pairs)
        self.assertEqual(len(hints), 1)
        row = hints[0]
        self.assertEqual(row["fulfillment_address_value"], self.pair_addr.value)
        self.assertEqual(row["yard_vehicle_kind_id"], self.vk.pk)
        self.assertEqual(row["yard_vehicle_kind_ids"], [self.vk.pk])
        self.assertEqual(row["vehicle_kind_id"], self.vk.pk)
