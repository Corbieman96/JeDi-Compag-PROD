from __future__ import annotations

from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ADMIN
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka, PruvodkaAttachment
from waste_docs.services.ride_attachment_print.stamp import stamp_attachment_pdf_bytes


def _minimal_pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=400, height=600)
    bio = BytesIO()
    writer.write(bio)
    return bio.getvalue()


def _pdf_extract_text(pdf_bytes: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(pdf_bytes))
    return "".join(page.extract_text() or "" for page in reader.pages)


class RideAttachmentStampTests(SimpleTestCase):
    def test_stamp_embeds_snd_and_date(self):
        snd = "0001400-2026-4"
        with patch(
            "waste_docs.services.ride_attachment_print.stamp._stamp_fitz",
            side_effect=ImportError("no fitz"),
        ):
            out = stamp_attachment_pdf_bytes(
                _minimal_pdf_bytes(),
                snd_cislo_listu=snd,
                drive_date=date(2026, 9, 11),
                ride_pk=4020,
            )
        text = _pdf_extract_text(out)
        self.assertIn(snd, text)
        self.assertIn("11.09.2026", text)


class RideAttachmentPrintViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("att_print_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.ride = Pruvodka.objects.create(
            name=NameCatalog.objects.create(value="Subjekt att print"),
            ico=IcoCatalog.objects.create(value="87654321"),
            address=AddressCatalog.objects.create(value="Adr att print"),
            waste_type=WasteTypeCatalog.objects.create(code="880088", value="Watt"),
            waste_code=WasteCodeCatalog.objects.create(value="WCATT"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOATT"),
            suffix=SuffixCatalog.objects.create(value="SFXATT"),
            drive_date=date(2026, 9, 11),
            vehicle_rz=VehicleRzCatalog.objects.create(value="2B22222"),
            vehicle_rz_snapshot="2B22222",
            created_by=self.user,
            container_number="",
            snd_cislo_listu="0001400-2026-4",
        )
        self.att = PruvodkaAttachment.objects.create(
            pruvodka=self.ride,
            sort_order=1,
            file=ContentFile(_minimal_pdf_bytes(), name="BRN3C2AF4C85008_012802.pdf"),
        )
        self.other_ride = Pruvodka.objects.create(
            name=self.ride.name,
            ico=self.ride.ico,
            address=self.ride.address,
            waste_type=self.ride.waste_type,
            waste_code=self.ride.waste_code,
            waste_category=self.ride.waste_category,
            suffix=self.ride.suffix,
            drive_date=date(2026, 9, 12),
            vehicle_rz=self.ride.vehicle_rz,
            vehicle_rz_snapshot="2B22222",
            created_by=self.user,
            container_number="",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_print_pdf_returns_stamped_bytes(self):
        self.ride.refresh_from_db()
        snd = (self.ride.snd_cislo_listu or "").strip()
        self.assertTrue(snd)
        url = reverse(
            "waste_docs:ride_attachment_print_pdf",
            kwargs={"pk": self.ride.pk, "att_pk": self.att.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        body = b"".join(response.streaming_content)
        text = _pdf_extract_text(body)
        self.assertIn(snd, text)
        self.assertIn("11.09.2026", text)

    def test_print_pdf_404_for_foreign_attachment(self):
        url = reverse(
            "waste_docs:ride_attachment_print_pdf",
            kwargs={"pk": self.other_ride.pk, "att_pk": self.att.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_detail_includes_attachment_print_config(self):
        response = self.client.get(reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "jedis-ride-attachment-print")
        self.assertContains(response, f"/waste-docs/{self.ride.pk}/attachments/{self.att.pk}/print.pdf")
        self.assertContains(response, "ride-attachment-print-open")
        self.assertContains(response, "Tisk s číslem jízdy")
        self.assertContains(response, "ride_attachment_print_prompt.js")
