from datetime import date
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from core.services.dashboard_print_links import (
    annotate_ride_groups_print_pks,
    dashboard_header_print_url,
    filter_pks_for_email_group,
    parse_selected_ride_pk,
    print_pks_for_group,
)


class DashboardPrintLinksTests(SimpleTestCase):
    def _group(self, pks):
        rides = []
        for pk in pks:
            ride = MagicMock()
            ride.pk = pk
            rides.append(ride)
        return {
            "drive_date": date(2026, 6, 10),
            "vehicle_rz_id": 20,
            "items": rides,
        }

    def test_parse_selected_ride_pk_valid(self):
        group = self._group([575, 576])
        self.assertEqual(parse_selected_ride_pk("575", group), 575)

    def test_parse_selected_ride_pk_invalid(self):
        group = self._group([575])
        self.assertIsNone(parse_selected_ride_pk("999", group))

    def test_filter_pks_for_email_group_selected_ride(self):
        group = self._group([575, 576])
        self.assertEqual(filter_pks_for_email_group(group, 576), [576])

    def test_filter_pks_for_email_group_all_items(self):
        group = self._group([575, 576])
        self.assertEqual(filter_pks_for_email_group(group, None), [575, 576])

    def test_print_pks_for_group_selected(self):
        group = self._group([575, 576])
        self.assertEqual(print_pks_for_group(group, 575), "575")

    def test_print_pks_for_group_single_item(self):
        group = self._group([575])
        self.assertEqual(print_pks_for_group(group, None), "575")

    def test_print_pks_for_group_multiple_without_selection(self):
        group = self._group([575, 576])
        self.assertEqual(print_pks_for_group(group, None), "")

    def test_annotate_ride_groups_print_pks(self):
        groups = [self._group([575, 576])]
        annotate_ride_groups_print_pks(groups, 576)
        self.assertEqual(groups[0]["print_pks"], "576")

    def test_dashboard_header_print_url_day_bulk_without_explicit_group(self):
        group = self._group([575, 576])
        url = dashboard_header_print_url(
            date(2026, 6, 10), group, None, ride_group_explicit=False
        )
        self.assertIn("dashboard-bulk", url)
        self.assertIn("date=2026-06-10", url)
        self.assertNotIn("pks=", url)
        self.assertNotIn("vehicle_rz_id=", url)

    def test_dashboard_header_print_url_scoped_to_ride_group(self):
        group = self._group([575, 576])
        url = dashboard_header_print_url(
            date(2026, 6, 10), group, None, ride_group_explicit=True
        )
        self.assertIn("pks=575,576", url)
        self.assertIn("vehicle_rz_id=20", url)

    def test_dashboard_header_print_url_scoped_to_ride_pk(self):
        group = self._group([575, 576])
        url = dashboard_header_print_url(
            date(2026, 6, 10), group, 575, ride_group_explicit=True
        )
        self.assertIn("pks=575", url)
        self.assertIn("vehicle_rz_id=20", url)
