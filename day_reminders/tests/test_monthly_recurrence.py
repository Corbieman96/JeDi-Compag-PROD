from datetime import date

from django.test import SimpleTestCase

from day_reminders.services.monthly_recurrence import (
    monthly_display,
    monthly_matches_date,
    nth_weekday_in_month,
    normalize_monthly_rule,
)


class MonthlyRecurrenceTests(SimpleTestCase):
    def test_first_wednesday_march_2026(self):
        rule = {"ordinal": 1, "weekday": 2}
        self.assertEqual(nth_weekday_in_month(2026, 3, 2, 1), date(2026, 3, 4))
        self.assertTrue(monthly_matches_date(rule, date(2026, 3, 4)))
        self.assertFalse(monthly_matches_date(rule, date(2026, 3, 11)))

    def test_last_friday_april_2026(self):
        rule = {"ordinal": -1, "weekday": 4}
        self.assertEqual(nth_weekday_in_month(2026, 4, 4, -1), date(2026, 4, 24))
        self.assertTrue(monthly_matches_date(rule, date(2026, 4, 24)))

    def test_fifth_weekday_missing_month(self):
        self.assertIsNone(nth_weekday_in_month(2026, 2, 0, 5))

    def test_display_first_wednesday(self):
        self.assertEqual(
            monthly_display({"ordinal": 1, "weekday": 2}),
            "Každý 1. středa v měsíci",
        )

    def test_normalize_rejects_invalid(self):
        with self.assertRaises(ValueError):
            normalize_monthly_rule({"ordinal": 5, "weekday": 2})
