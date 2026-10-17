from __future__ import annotations

import tempfile
from datetime import date, datetime, timezone as dt_timezone
from pathlib import Path

from django.test import TestCase, override_settings

from waste_docs.models import Pruvodka
from waste_docs.services.ride_bulk_actions import append_day_protocol_file


class DashboardBulkProtocolTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_protocol_found_when_ride_order_differs(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            protocol_dir = media / "protokoly"
            protocol_dir.mkdir(parents=True)
            (protocol_dir / "protokol_den_2026-03-01.pdf").write_bytes(b"%PDF")

            ride_a = Pruvodka(
                pk=1,
                snd_cislo_listu="0000283-2026-1",
                drive_date=date(2026, 3, 1),
                created_at=datetime(2026, 3, 1, 12, 0, tzinfo=dt_timezone.utc),
            )
            ride_b = Pruvodka(
                pk=2,
                snd_cislo_listu="0000280-2026",
                drive_date=date(2026, 3, 1),
                created_at=datetime(2026, 3, 1, 9, 0, tzinfo=dt_timezone.utc),
            )
            # Denní protokol se hledá podle data, ne podle SND první jízdy.
            protocol_rides = [ride_b, ride_a]
            display_rides_wrong = [ride_a, ride_b]

            with override_settings(MEDIA_ROOT=media):
                wrong_rows = append_day_protocol_file(
                    [],
                    display_rides_wrong,
                    date(2026, 3, 1),
                    generate_if_missing=False,
                )
                good_rows = append_day_protocol_file(
                    [],
                    protocol_rides,
                    date(2026, 3, 1),
                    generate_if_missing=False,
                )

            self.assertEqual(len(wrong_rows), 1)
            self.assertEqual(len(good_rows), 1)
            self.assertEqual(good_rows[0]["kind"], "protocol")
            self.assertTrue(good_rows[0]["path"].endswith(".pdf"))
