from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
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
from waste_docs.services.pruvodka_attachments import append_upload_snapshot_to_pruvodka


@patch("waste_docs.views.pruvodka_edit.city_from_coords", return_value="Česko")
class PruvodkaEditAttachmentsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("edit_att_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.ride_date = date(2027, 4, 10)
        self.name = NameCatalog.objects.create(value="Subjekt edit att")
        self.ride = Pruvodka.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="55667788"),
            address=AddressCatalog.objects.create(value="Ulice, 1, Město"),
            waste_type=WasteTypeCatalog.objects.create(code="990096", value="Wea"),
            waste_code=WasteCodeCatalog.objects.create(value="WCEA"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOEA"),
            suffix=SuffixCatalog.objects.create(value="SFXEA"),
            drive_date=self.ride_date,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P66666"),
            container_number="",
            created_by=self.admin,
        )
        self.edit_url = reverse("waste_docs:edit", kwargs={"pk": self.ride.pk})
        self.client = Client()
        self.client.force_login(self.admin)

    def _edit_post_data(self) -> dict[str, str]:
        return {
            "drive_date": self.ride.drive_date.strftime("%Y-%m-%d"),
            "name": str(self.ride.name_id),
            "ico": str(self.ride.ico_id),
            "waste_type": str(self.ride.waste_type_id),
            "suffix": str(self.ride.suffix_id),
            "vehicle_rz": str(self.ride.vehicle_rz_id),
            "fulfillment_address_value": self.ride.address.value,
            "container_number": "",
            "container_number_2": "",
            "contact_phone": "",
            "contract_number": "",
            "contact_note": "",
            "repeat_count": "1",
        }

    def test_edit_shows_existing_attachment_and_remaining_slots(self, _mock_city):
        PruvodkaAttachment.objects.create(
            pruvodka=self.ride,
            sort_order=1,
            file=ContentFile(b"existing", name="existing.pdf"),
        )
        response = self.client.get(self.edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stávající přílohy")
        self.assertContains(response, "existing")
        self.assertContains(response, 'name="attachment_1"')
        self.assertContains(response, 'name="attachment_2"')

    def test_edit_post_adds_attachment(self, _mock_city):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                upload = SimpleUploadedFile("new-doc.pdf", b"%PDF-new", content_type="application/pdf")
                response = self.client.post(
                    self.edit_url,
                    {**self._edit_post_data(), "attachment_1": upload},
                )
                self.assertRedirects(
                    response,
                    reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}),
                )
                self.ride.refresh_from_db()
                self.assertEqual(self.ride.attachments.count(), 1)

    def test_append_respects_max_three_attachments(self, _mock_city):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                for i in range(1, 4):
                    PruvodkaAttachment.objects.create(
                        pruvodka=self.ride,
                        sort_order=i,
                        file=ContentFile(f"old{i}".encode(), name=f"old{i}.pdf"),
                    )
                added = append_upload_snapshot_to_pruvodka(self.ride, [("extra.pdf", b"x")])
                self.assertEqual(added, 0)
                self.assertEqual(self.ride.attachments.count(), 3)

    def test_edit_with_three_attachments_shows_only_links(self, _mock_city):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media):
                for i in range(1, 4):
                    PruvodkaAttachment.objects.create(
                        pruvodka=self.ride,
                        sort_order=i,
                        file=ContentFile(f"file{i}".encode(), name=f"file{i}.pdf"),
                    )
                response = self.client.get(self.edit_url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "file1.pdf")
                self.assertContains(response, "file3.pdf")
                self.assertNotContains(response, 'name="attachment_1"')

    def test_edit_form_offers_only_remaining_attachment_slots(self, _mock_city):
        from waste_docs.forms import PruvodkaForm

        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                for i in range(1, 3):
                    PruvodkaAttachment.objects.create(
                        pruvodka=self.ride,
                        sort_order=i,
                        file=ContentFile(f"old{i}".encode(), name=f"old{i}.pdf"),
                    )
                form = PruvodkaForm(instance=self.ride, is_edit=True, user=self.admin)
                self.assertEqual(form.attachment_upload_slots, [1])
