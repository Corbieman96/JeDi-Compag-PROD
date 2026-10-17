"""Dvě různé adresy v průvodce: ADRESA_ = provozovna, MISTO_DODANI = plnění."""

from __future__ import annotations

from django.test import TestCase

from catalogs.models import AddressCatalog, IcoCatalog, NameCatalog, NameSubjectProfile
from waste_docs.models import Pruvodka
from waste_docs.pruvodka_services import _placeholder_values


class AdresaPlaceholderFacilityTests(TestCase):
    databases = {"default", "addresses"}

    def test_adresa_and_misto_never_swapped(self):
        name = NameCatalog.objects.create(value="Firma ADRESA test")
        ico = IcoCatalog.objects.create(value="99887766")
        facility = AddressCatalog.objects.create(value="Provozovna 1, 100, Město")
        fulfillment = AddressCatalog.objects.create(value="Plnění 2, 200, Vesnice")
        profile = NameSubjectProfile.objects.create(name=name, ico=ico)
        profile.facility_address = facility
        profile.fulfillment_address = fulfillment
        profile.address_profile.save()

        ride = Pruvodka(
            name=name,
            name_snapshot=name.value,
            ico_snapshot=ico.value,
            address=fulfillment,
            address_snapshot=fulfillment.value,
        )
        values = _placeholder_values(ride)
        adresa = values["{{ADRESA_}}"]
        misto = values["{{MISTO_DODANI_CINNOST_}}"]

        self.assertEqual(adresa, f"{facility.value} / {ico.value}")
        self.assertEqual(misto, fulfillment.value)
        self.assertNotIn(fulfillment.value, adresa)
        self.assertNotIn(facility.value, misto)
        self.assertEqual(values["{{KDO_ADDRESS}}"], fulfillment.value)

    def test_misto_prefers_live_address_fk(self):
        name = NameCatalog.objects.create(value="Firma FK plnění")
        ico = IcoCatalog.objects.create(value="55667788")
        facility = AddressCatalog.objects.create(value="Provozovna FK, 1, A")
        live = AddressCatalog.objects.create(value="Plnění živé, 9, B")
        profile = NameSubjectProfile.objects.create(name=name, ico=ico)
        profile.facility_address = facility
        profile.address_profile.save()

        ride = Pruvodka(
            name=name,
            ico_snapshot=ico.value,
            address=live,
            address_snapshot="Zastaralý snapshot plnění",
        )
        values = _placeholder_values(ride)
        self.assertEqual(values["{{MISTO_DODANI_CINNOST_}}"], live.value)
        self.assertIn(facility.value, values["{{ADRESA_}}"])
        self.assertNotIn(live.value, values["{{ADRESA_}}"])

    def test_adresa_ico_only_when_facility_missing(self):
        name = NameCatalog.objects.create(value="Bez provozovny")
        ico = IcoCatalog.objects.create(value="11223344")
        NameSubjectProfile.objects.create(name=name, ico=ico)
        ride = Pruvodka(
            name=name,
            ico_snapshot=ico.value,
            address_snapshot="Jen plnění, 1, X",
        )
        values = _placeholder_values(ride)
        self.assertEqual(values["{{ADRESA_}}"], ico.value)
        self.assertEqual(values["{{MISTO_DODANI_CINNOST_}}"], "Jen plnění, 1, X")
        self.assertNotIn("Jen plnění", values["{{ADRESA_}}"])
