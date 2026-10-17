from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from waste_docs.services.reports.protocol_note_overflow import (
    PROTOCOL_NOTE_FONT,
    build_protocol_note_supplement_pdf_bytes,
    protocol_note_for_cell,
    rides_needing_note_supplement,
)


class ProtocolNoteOverflowTests(SimpleTestCase):
    def _ride(self, pk: int, note: str):
        ride = MagicMock()
        ride.pk = pk
        ride.contact_note = note
        ride.snd_cislo_listu = "2026-0610-01"
        ride.drive_date = date(2026, 6, 10)
        ride.vehicle_rz_snapshot = "8S74311"
        ride.driver_snapshot = "Jan Vágner"
        ride.driver_id = None
        ride.driver = None
        ride.name_snapshot = "ABC s.r.o."
        ride.address_snapshot = "Praha 1"
        ride.waste_type_snapshot = "Komunální"
        ride.suffix_snapshot = "Spalovna"
        ride.activity_id = None
        return ride

    def test_short_note_fits_in_cell(self):
        text, needs = protocol_note_for_cell("Vjezd zezadu")
        self.assertEqual(text, "Vjezd zezadu")
        self.assertFalse(needs)

    def test_long_note_truncated_with_suffix(self):
        long_note = "Zavolat patnáct minut předem na číslo, vjezd zezadu areálu, brána vpravo od skladu, kontaktovat pana Nováka u vrátnice."
        text, needs = protocol_note_for_cell(long_note)
        self.assertTrue(needs)
        self.assertIn("(viz list Poznámky)", text)
        self.assertLess(len(text), len(long_note))

    def test_rides_needing_supplement(self):
        rides = [
            self._ride(1, "Krátká"),
            self._ride(2, "x" * 120),
        ]
        out = rides_needing_note_supplement(rides)
        self.assertEqual([r.pk for r in out], [2])

    def test_supplement_pdf_bytes_nonempty(self):
        ride = self._ride(1, "x" * 120)
        data = build_protocol_note_supplement_pdf_bytes([ride])
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 200)

    def test_empty_note_no_supplement_pdf(self):
        self.assertEqual(build_protocol_note_supplement_pdf_bytes([self._ride(1, "")]), b"")

    def test_supplement_pdf_preserves_czech_diacritics(self):
        if PROTOCOL_NOTE_FONT == "Helvetica":
            self.skipTest("Unicode TTF není k dispozici")
        from pypdf import PdfReader

        note = (
            "Přistavit až po obědě, čelem k chodníku. "
            + ("kontaktovat řidiče, " * 20)
        )
        ride = self._ride(1, note)
        ride.driver_snapshot = "Aleš Suchánek"
        ride.address_snapshot = "Jiřínská, 1350, Mladá Boleslav"
        ride.waste_type_snapshot = "Směsné stavební a demoliční odpady"
        data = build_protocol_note_supplement_pdf_bytes([ride])
        text = "".join((page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages)
        self.assertIn("Poznámka k jízdě", text)
        self.assertIn("Řidič", text)
        self.assertIn("Přistavit", text)
        self.assertIn("obědě", text)
        self.assertIn("čelem", text)
        self.assertIn("Suchánek", text)

    def test_supplement_pdf_koncovka_on_own_line(self):
        if PROTOCOL_NOTE_FONT == "Helvetica":
            self.skipTest("Unicode TTF není k dispozici")
        from pypdf import PdfReader

        ride = self._ride(1, "x" * 120)
        ride.waste_type_snapshot = (
            "Směsné stavební a demoliční odpady neuvedené pod čísly "
            "17 09 01, 17 09 02 a 17 09 03"
        )
        ride.suffix_snapshot = "Spalovna XYZ"
        data = build_protocol_note_supplement_pdf_bytes([ride])
        text = "".join((page.extract_text() or "") for page in PdfReader(BytesIO(data)).pages)
        self.assertIn("Koncovka:", text)
        self.assertIn("Spalovna XYZ", text)
        self.assertNotIn("·  Koncovka:", text)
        self.assertNotIn("· Koncovka:", text)
