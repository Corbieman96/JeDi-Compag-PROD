from django.test import TestCase

from catalogs.models import (
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    SuffixSiteProfile,
    WasteTypeCatalog,
)
from pio.xlsx_generate import format_pio_koncovka_placeholder, user_pio_placeholder_map


class FormatPioKoncovkaPlaceholderTests(TestCase):
    def test_with_icz_prefixes_label(self):
        suffix = SuffixCatalog.objects.create(value="Cihlářský Závod")
        SuffixSiteProfile.objects.create(suffix=suffix, name="Cihlářský Závod", icz="570974")
        self.assertEqual(
            format_pio_koncovka_placeholder(suffix),
            "IČZ: 570974 Cihlářský Závod",
        )

    def test_without_site_profile_returns_label_only(self):
        suffix = SuffixCatalog.objects.create(value="Jen koncovka")
        self.assertEqual(format_pio_koncovka_placeholder(suffix), "Jen koncovka")

    def test_empty_icz_returns_label_only(self):
        suffix = SuffixCatalog.objects.create(value="Koncovka bez IČZ")
        SuffixSiteProfile.objects.create(suffix=suffix, name="Koncovka bez IČZ", icz="")
        self.assertEqual(format_pio_koncovka_placeholder(suffix), "Koncovka bez IČZ")

    def test_none_suffix_returns_empty(self):
        self.assertEqual(format_pio_koncovka_placeholder(None), "")


class UserPioPlaceholderKoncovkaTests(TestCase):
    def setUp(self):
        name = NameCatalog.objects.create(value="Subjekt PIO IČZ")
        self.subject = NameSubjectProfile.objects.create(
            name=name,
            company_name="Test firma",
            pio_officer_name="Novák",
            pio_officer_phone="123",
            pio_officer_email="a@b.cz",
        )
        self.waste = WasteTypeCatalog.objects.create(code="17 05 04", value="Odpad")
        self.suffix = SuffixCatalog.objects.create(value="Překladiště Michalovice")
        SuffixSiteProfile.objects.create(
            suffix=self.suffix,
            name="Překladiště Michalovice",
            icz="123456",
        )
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.waste,
            suffix=self.suffix,
        )

    def test_user_pio_map_includes_icz_in_koncovka(self):
        values = user_pio_placeholder_map(self.subject, waste_suffix_pair=self.pair)
        self.assertEqual(values["{{koncovka}}"], "IČZ: 123456 Překladiště Michalovice")
