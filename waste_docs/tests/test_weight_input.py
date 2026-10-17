"""Parsování hmotnosti a Excel placeholder."""

from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from waste_docs.pruvodka_services import _placeholder_values
from waste_docs.services.weight_input import (
    format_weight_snapshot,
    parse_weight_t,
    weight_must_be_positive_error,
)


class WeightInputTests(SimpleTestCase):
    def test_parse_accepts_comma_and_dot(self):
        self.assertEqual(parse_weight_t("100"), Decimal("100"))
        self.assertEqual(parse_weight_t("100,2"), Decimal("100.2"))
        self.assertEqual(parse_weight_t("100.2"), Decimal("100.2"))

    def test_parse_rejects_invalid(self):
        self.assertIsNone(parse_weight_t(""))
        self.assertIsNone(parse_weight_t("abc"))

    def test_positive_validation(self):
        self.assertIsNotNone(weight_must_be_positive_error(None))
        self.assertIsNotNone(weight_must_be_positive_error(Decimal("0")))
        self.assertIsNotNone(weight_must_be_positive_error(Decimal("-1")))
        self.assertIsNone(weight_must_be_positive_error(Decimal("0.1")))

    def test_format_snapshot(self):
        self.assertEqual(format_weight_snapshot(Decimal("100")), "100")
        self.assertEqual(format_weight_snapshot(Decimal("100.2")), "100,2")


class WeightPlaceholderTests(TestCase):
    def test_placeholder_empty_without_weight(self):
        from waste_docs.models import Pruvodka

        ride = Pruvodka(weight_snapshot="")
        values = _placeholder_values(ride)
        self.assertEqual(values.get("{{HMOTNOST_}}"), "")

    def test_placeholder_with_weight_snapshot(self):
        from waste_docs.models import Pruvodka

        ride = Pruvodka(weight_snapshot="100,2")
        values = _placeholder_values(ride)
        self.assertEqual(values.get("{{HMOTNOST_}}"), "100,2")
