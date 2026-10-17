from __future__ import annotations

from datetime import date, datetime, timezone as dt_timezone
from email import message_from_bytes
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
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
from waste_docs.models import Pruvodka, RideEmailRecipient, RideGroupEmailDispatch
from waste_docs.services.ride_document_email.recipient_presets import add_recipient, touch_recipient_used
from waste_docs.services.ride_document_email.dispatch_record import cancel_group_dispatch, record_group_dispatch
from waste_docs.services.ride_document_email.eml_build import EmailAttachment, build_eml_bytes
from waste_docs.services.ride_document_email.exclusions import is_group_emailed
from waste_docs.services.ride_document_email.group_attachments import (
    GroupEmailPackage,
    build_group_email_package,
)
from waste_docs.services.ride_bulk_actions import build_print_rows_and_files, rides_for_print_scope
from waste_docs.services.ride_protocol_xlsx import rides_for_protocol_group


class RideGroupEmailDispatchModelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_dispatch_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 6, 10)
        self.rz = VehicleRzCatalog.objects.create(value="9E99999")

    def test_record_and_cancel_group_dispatch(self):
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="test@example.com",
            subject="Subjekt test",
            ride_count=2,
            attachment_count=2,
            user=self.user,
        )
        self.assertTrue(is_group_emailed(self.drive_date, self.rz.pk))
        cancelled = cancel_group_dispatch(self.drive_date, self.rz.pk)
        self.assertTrue(cancelled)
        self.assertFalse(is_group_emailed(self.drive_date, self.rz.pk))

    def test_resend_updates_existing_row(self):
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="first@example.com",
            subject="Prvni",
            ride_count=1,
            attachment_count=2,
            user=self.user,
        )
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="second@example.com",
            subject="Druhy",
            ride_count=3,
            attachment_count=2,
            user=self.user,
        )
        self.assertEqual(RideGroupEmailDispatch.objects.count(), 1)
        row = RideGroupEmailDispatch.objects.get()
        self.assertEqual(row.recipient_email, "second@example.com")
        self.assertEqual(row.ride_count, 3)


class RideGroupEmailExclusionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_excl_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 6, 11)
        self.rz = VehicleRzCatalog.objects.create(value="8E88888")
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt email excl"),
            ico=IcoCatalog.objects.create(value="99887766"),
            address=AddressCatalog.objects.create(value="Adr email"),
            waste_type=WasteTypeCatalog.objects.create(code="881122", value="Wemail"),
            waste_code=WasteCodeCatalog.objects.create(value="WCEM"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOEM"),
            suffix=SuffixCatalog.objects.create(value="SFXEM"),
            drive_date=self.drive_date,
            created_by=self.user,
            container_number="",
        )
        self.ride = Pruvodka.objects.create(
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="8E88888",
            ride_group_number=300,
            ride_sequence=1,
            created_at=datetime(2026, 6, 11, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="disp@example.com",
            subject="Test",
            ride_count=1,
            attachment_count=2,
            user=self.user,
        )

    def test_build_print_rows_skips_emailed_group(self):
        _rows, file_rows, _warnings = build_print_rows_and_files([self.ride])
        self.assertEqual(file_rows, [])

    @patch("waste_docs.services.ride_bulk_actions.has_generated_excel_file", return_value=True)
    def test_build_print_rows_includes_emailed_group_for_email_package(self, _mock_has_excel):
        self.ride.generated_file = MagicMock()
        self.ride.generated_file.name = "pruvodky/test.xlsx"
        self.ride.generated_file.url = "/media/pruvodky/test.xlsx"
        self.ride.generated_file.path = "/tmp/pruvodky/test.xlsx"
        _rows, file_rows, _warnings = build_print_rows_and_files(
            [self.ride],
            for_email_package=True,
        )
        self.assertEqual(len(file_rows), 1)
        self.assertEqual(file_rows[0]["kind"], "xlsx")

    def test_rides_for_print_scope_includes_emailed_group_for_email_package(self):
        rides = rides_for_print_scope(
            self.drive_date,
            self.user,
            vehicle_rz_id=self.rz.pk,
            for_email_package=True,
        )
        self.assertEqual(len(rides), 1)
        self.assertEqual(rides[0].pk, self.ride.pk)

    def test_protocol_group_empty_when_emailed(self):
        self.assertEqual(rides_for_protocol_group(self.drive_date, self.rz.pk, self.user), [])

    def test_protocol_group_includes_emailed_when_for_email_package(self):
        rides = rides_for_protocol_group(
            self.drive_date,
            self.rz.pk,
            self.user,
            for_email_package=True,
        )
        self.assertEqual(len(rides), 1)
        self.assertEqual(rides[0].pk, self.ride.pk)


class RideGroupEmailDriverScopeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_drv_scope", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 6, 15)
        self.rz = VehicleRzCatalog.objects.create(value="4E44444")
        from catalogs.models import DriverProfile

        self.driver_a = DriverProfile.objects.create(personal_number="EM-A", last_name="Horák")
        self.driver_b = DriverProfile.objects.create(personal_number="EM-B", last_name="Dvořák")
        common = dict(
            name=NameCatalog.objects.create(value="Subj email drv"),
            ico=IcoCatalog.objects.create(value="55443322"),
            address=AddressCatalog.objects.create(value="Adr drv"),
            waste_type=WasteTypeCatalog.objects.create(code="885566", value="Wdrv"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDR"),
            waste_category=WasteCategoryCatalog.objects.create(value="KODR"),
            suffix=SuffixCatalog.objects.create(value="SFXDR"),
            drive_date=self.drive_date,
            created_by=self.user,
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="4E44444",
            container_number="",
        )
        self.ride_a = Pruvodka.objects.create(driver=self.driver_a, **common)
        self.ride_b = Pruvodka.objects.create(driver=self.driver_b, **common)

    def test_rides_for_print_scope_filters_by_driver(self):
        rides_a = rides_for_print_scope(
            self.drive_date,
            self.user,
            vehicle_rz_id=self.rz.pk,
            driver_id=self.driver_a.pk,
        )
        self.assertEqual([r.pk for r in rides_a], [self.ride_a.pk])

    def test_rides_for_print_scope_without_driver_returns_all_rz_rides(self):
        rides = rides_for_print_scope(
            self.drive_date,
            self.user,
            vehicle_rz_id=self.rz.pk,
        )
        self.assertEqual(len(rides), 2)

    def test_rides_for_print_scope_filter_pks_overrides_driver_mismatch(self):
        rides = rides_for_print_scope(
            self.drive_date,
            self.user,
            vehicle_rz_id=self.rz.pk,
            driver_id=0,
            filter_pks=[self.ride_a.pk],
        )
        self.assertEqual([r.pk for r in rides], [self.ride_a.pk])

    def test_protocol_group_filters_by_driver(self):
        rides_a = rides_for_protocol_group(
            self.drive_date,
            self.rz.pk,
            self.user,
            driver_id=self.driver_b.pk,
            for_email_package=True,
        )
        self.assertEqual([r.pk for r in rides_a], [self.ride_b.pk])


class RideGroupEmailPackageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_pkg_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.drive_date = date(2026, 6, 14)
        self.rz = VehicleRzCatalog.objects.create(value="5E55555")
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt email pkg"),
            ico=IcoCatalog.objects.create(value="66554433"),
            address=AddressCatalog.objects.create(value="Adr pkg"),
            waste_type=WasteTypeCatalog.objects.create(code="884455", value="Wpkg"),
            waste_code=WasteCodeCatalog.objects.create(value="WCPK"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOPK"),
            suffix=SuffixCatalog.objects.create(value="SFXPK"),
            drive_date=self.drive_date,
            created_by=self.user,
            container_number="",
        )
        self.ride = Pruvodka.objects.create(
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="5E55555",
            ride_group_number=600,
            ride_sequence=1,
            created_at=datetime(2026, 6, 14, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="sent@example.com",
            subject="Odeslano",
            ride_count=1,
            attachment_count=2,
            user=self.user,
        )

    @patch("waste_docs.services.ride_document_email.group_attachments.convert_xlsx_to_pdf")
    @patch("waste_docs.services.ride_document_email.group_attachments.generate_protocol_xlsx")
    @patch("waste_docs.services.ride_document_email.group_attachments._merge_file_rows_to_bytes")
    @patch("waste_docs.services.ride_document_email.group_attachments.build_print_rows_and_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.prepare_print_bundle_files")
    def test_build_group_email_package_when_group_already_emailed(
        self,
        _mock_prepare,
        mock_rows,
        mock_merge,
        mock_gen_protocol,
        mock_convert,
    ):
        from pathlib import Path

        mock_rows.return_value = (
            [],
            [
                {
                    "kind": "xlsx",
                    "label": "Průvodka",
                    "url": "/m/x.xlsx",
                    "media_rel": "x.xlsx",
                    "print_url": "/waste-docs/print/x.xlsx",
                }
            ],
            [],
        )
        mock_merge.return_value = b"%PDF pruvodky zpo"
        protocol_xlsx = Path("/tmp/protokol.xlsx")
        mock_gen_protocol.return_value = protocol_xlsx
        pdf_path = MagicMock()
        pdf_path.read_bytes.return_value = b"%PDF protokol"
        mock_convert.return_value = pdf_path
        with patch(
            "waste_docs.services.ride_document_email.group_attachments.settings.MEDIA_ROOT",
            Path("/tmp"),
        ):
            package = build_group_email_package(
                drive_date=self.drive_date,
                vehicle_rz_id=self.rz.pk,
                user=self.user,
                driver_id=0,
                filter_pks=[self.ride.pk],
            )
        self.assertTrue(mock_rows.call_args.kwargs.get("for_email_package"))
        self.assertEqual(package.pruvodky_zpo_pdf, b"%PDF pruvodky zpo")
        self.assertEqual(package.protocol_pdf, b"%PDF protokol")
        self.assertEqual(package.ride_count, 1)

    @patch("waste_docs.services.ride_document_email.group_attachments.prepare_print_bundle_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.build_print_rows_and_files")
    def test_build_group_email_package_clear_error_when_no_printable(
        self,
        mock_rows,
        _mock_prepare,
    ):
        from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError

        mock_rows.return_value = ([], [], [])
        with self.assertRaises(XlsxToPdfError) as ctx:
            build_group_email_package(
                drive_date=self.drive_date,
                vehicle_rz_id=self.rz.pk,
                user=self.user,
                driver_id=0,
                filter_pks=[self.ride.pk],
            )
        self.assertIn("průvodky", str(ctx.exception).lower())
        self.assertNotIn("pro vybranou volbu", str(ctx.exception).lower())

    @patch("waste_docs.services.ride_document_email.group_attachments.prepare_print_bundle_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.build_print_rows_and_files")
    def test_build_group_email_package_fails_on_zpo_warnings(
        self,
        mock_rows,
        _mock_prepare,
    ):
        from waste_docs.services.reports.xlsx_to_pdf import XlsxToPdfError

        mock_rows.return_value = (
            [],
            [
                {
                    "kind": "xlsx",
                    "label": "Průvodka",
                    "url": "/m/x.xlsx",
                    "media_rel": "x.xlsx",
                    "print_url": "/waste-docs/print/x.xlsx",
                }
            ],
            ["#1 (0000100)"],
        )
        with self.assertRaises(XlsxToPdfError) as ctx:
            build_group_email_package(
                drive_date=self.drive_date,
                vehicle_rz_id=self.rz.pk,
                user=self.user,
                driver_id=0,
                filter_pks=[self.ride.pk],
            )
        self.assertIn("ZPO", str(ctx.exception))

    @patch("waste_docs.services.ride_document_email.group_attachments.convert_xlsx_to_pdf")
    @patch("waste_docs.services.ride_document_email.group_attachments.generate_protocol_xlsx")
    @patch("waste_docs.services.ride_document_email.group_attachments._merge_file_rows_to_bytes")
    @patch("waste_docs.services.ride_document_email.group_attachments.build_print_rows_and_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.prepare_print_bundle_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.should_generate_excel", return_value=False)
    def test_build_group_email_package_without_excel_has_zpo_and_protocol(
        self,
        _mock_should_excel,
        _mock_prepare,
        mock_rows,
        mock_merge,
        mock_gen_protocol,
        mock_convert,
    ):
        from pathlib import Path

        mock_rows.return_value = (
            [],
            [
                {
                    "kind": "zpo",
                    "label": "ZPO #1",
                    "url": "/media/zpo/test.pdf",
                    "path": "/tmp/zpo/test.pdf",
                    "print_url": "/media/zpo/test.pdf",
                }
            ],
            [],
        )
        mock_merge.return_value = b"%PDF zpo only"
        protocol_xlsx = Path("/tmp/protokol.xlsx")
        mock_gen_protocol.return_value = protocol_xlsx
        pdf_path = MagicMock()
        pdf_path.read_bytes.return_value = b"%PDF protokol"
        mock_convert.return_value = pdf_path
        with patch(
            "waste_docs.services.ride_document_email.group_attachments.settings.MEDIA_ROOT",
            Path("/tmp"),
        ):
            package = build_group_email_package(
                drive_date=self.drive_date,
                vehicle_rz_id=self.rz.pk,
                user=self.user,
                driver_id=0,
                filter_pks=[self.ride.pk],
            )
        self.assertEqual(package.pruvodky_zpo_pdf, b"%PDF zpo only")
        self.assertTrue(package.pruvodky_zpo_filename.startswith("zpo_"))
        self.assertEqual(package.protocol_pdf, b"%PDF protokol")

    @patch("waste_docs.services.ride_document_email.group_attachments.convert_xlsx_to_pdf")
    @patch("waste_docs.services.ride_document_email.group_attachments.generate_protocol_xlsx")
    @patch("waste_docs.services.ride_document_email.group_attachments.build_print_rows_and_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.prepare_print_bundle_files")
    @patch("waste_docs.services.ride_document_email.group_attachments.should_generate_excel", return_value=False)
    def test_build_group_email_package_without_excel_protocol_only(
        self,
        _mock_should_excel,
        _mock_prepare,
        mock_rows,
        mock_gen_protocol,
        mock_convert,
    ):
        from pathlib import Path

        mock_rows.return_value = ([], [], [])
        protocol_xlsx = Path("/tmp/protokol.xlsx")
        mock_gen_protocol.return_value = protocol_xlsx
        pdf_path = MagicMock()
        pdf_path.read_bytes.return_value = b"%PDF protokol"
        mock_convert.return_value = pdf_path
        with patch(
            "waste_docs.services.ride_document_email.group_attachments.settings.MEDIA_ROOT",
            Path("/tmp"),
        ):
            package = build_group_email_package(
                drive_date=self.drive_date,
                vehicle_rz_id=self.rz.pk,
                user=self.user,
                driver_id=0,
                filter_pks=[self.ride.pk],
            )
        self.assertIsNone(package.pruvodky_zpo_pdf)
        self.assertEqual(package.protocol_pdf, b"%PDF protokol")


class RideGroupEmailSubjectBodyTests(TestCase):
    def test_body_lists_merged_and_protocol(self):
        from waste_docs.services.ride_document_email.subject_body import build_group_email_body

        body = build_group_email_body(
            vehicle_rz="9S06217",
            drive_date=date(2026, 6, 22),
            ride_count=4,
            has_merged_docs=True,
            has_protocol=True,
        )
        self.assertIn("průvodky a/nebo ZPO", body)
        self.assertIn("protokol jízd", body)

    def test_body_protocol_only(self):
        from waste_docs.services.ride_document_email.subject_body import build_group_email_body

        body = build_group_email_body(
            vehicle_rz="9S06217",
            drive_date=date(2026, 6, 22),
            ride_count=4,
            has_merged_docs=False,
            has_protocol=True,
        )
        self.assertNotIn("průvodky a/nebo ZPO", body)
        self.assertIn("protokol jízd", body)


class RideGroupEmailEmlTests(TestCase):
    def test_build_eml_has_two_pdf_attachments(self):
        payload = build_eml_bytes(
            from_email="odesilatel@example.com",
            recipient_email="prijemce@example.com",
            subject="Pruvodky a protokol",
            body="Text",
            attachments=[
                EmailAttachment(filename="pruvodky_zpo.pdf", data=b"%PDF-1.4 pruvodky"),
                EmailAttachment(filename="protokol.pdf", data=b"%PDF-1.4 protokol"),
            ],
        )
        msg = message_from_bytes(payload)
        self.assertEqual(msg["From"], "odesilatel@example.com")
        self.assertEqual(msg["To"], "prijemce@example.com")
        self.assertEqual(str(msg["Subject"]), "Pruvodky a protokol")
        filenames = []
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filenames.append(part.get_filename())
        self.assertEqual(filenames, ["pruvodky_zpo.pdf", "protokol.pdf"])

    def test_build_eml_has_outlook_draft_headers(self):
        payload = build_eml_bytes(
            recipient_email="ridic@firma.cz",
            subject="Test koncept",
            body="Telo",
            attachments=[EmailAttachment(filename="a.pdf", data=b"%PDF")],
        )
        msg = message_from_bytes(payload)
        self.assertEqual(msg["X-Unsent"], "1")
        self.assertIsNone(msg["From"])
        self.assertIn(b"X-Unsent: 1", payload)

    def test_build_eml_sets_reply_to_when_given(self):
        payload = build_eml_bytes(
            recipient_email="ridic@firma.cz",
            subject="Test",
            body="Telo",
            attachments=[EmailAttachment(filename="a.pdf", data=b"%PDF")],
            reply_to="dispecer@firma.cz",
        )
        msg = message_from_bytes(payload)
        self.assertEqual(msg["Reply-To"], "dispecer@firma.cz")
        self.assertIsNone(msg["From"])


class RideGroupEmailFromAddressTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            "from_addr_user",
            password="pw",
            email="dispecer@firma.cz",
            first_name="Jan",
            last_name="Novák",
        )

    def test_resolve_group_email_from_header_outlook_format(self):
        from email.utils import parseaddr

        from waste_docs.services.ride_document_email.from_address import resolve_group_email_from_header

        header = resolve_group_email_from_header(self.user)
        _name, addr = parseaddr(header)
        self.assertEqual(addr, "dispecer@firma.cz")
        self.assertTrue(header.endswith("<dispecer@firma.cz>"))

    def test_require_user_sender_email_raises_when_missing(self):
        from waste_docs.services.ride_document_email.from_address import require_user_sender_email

        User = get_user_model()
        bare = User.objects.create_user("no_email_user", password="pw")
        with self.assertRaises(ValueError):
            require_user_sender_email(bare)


class RideGroupEmailViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            "email_view_user",
            password="pw",
            email="odesilatel@firma.cz",
            first_name="Dispečer",
            is_superuser=True,
        )
        set_user_role(self.user, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2026, 6, 12)
        self.rz = VehicleRzCatalog.objects.create(value="7E77777")
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt email view"),
            ico=IcoCatalog.objects.create(value="88776655"),
            address=AddressCatalog.objects.create(value="Adr view"),
            waste_type=WasteTypeCatalog.objects.create(code="882233", value="Wview"),
            waste_code=WasteCodeCatalog.objects.create(value="WCVW"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOVW"),
            suffix=SuffixCatalog.objects.create(value="SFXVW"),
            drive_date=self.drive_date,
            created_by=self.user,
            container_number="",
        )
        self.ride = Pruvodka.objects.create(
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="7E77777",
            ride_group_number=400,
            ride_sequence=1,
            created_at=datetime(2026, 6, 12, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )
        self.package = GroupEmailPackage(
            pruvodky_zpo_pdf=b"%PDF pruvodky",
            pruvodky_zpo_filename="pruvodky_zpo_test.pdf",
            protocol_pdf=b"%PDF protokol",
            protocol_filename="protokol_test.pdf",
            ride_count=1,
            vehicle_rz_label="7E77777",
        )

    @patch("waste_docs.views.ride_document_email.prepare.build_group_email_package")
    def test_prepare_returns_eml(self, mock_build):
        mock_build.return_value = self.package
        url = reverse("waste_docs:ride_group_email_prepare")
        resp = self.client.post(
            url,
            data='{"date":"2026-06-12","vehicle_rz_id":%d,"recipient_email":"prijemce@example.com"}'
            % self.rz.pk,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("message/rfc822", resp["Content-Type"])
        self.assertIn("inline", resp["Content-Disposition"])
        msg = message_from_bytes(b"".join(resp.streaming_content))
        self.assertEqual(msg["To"], "prijemce@example.com")
        self.assertIsNone(msg["From"])
        self.assertEqual(msg["Reply-To"], "odesilatel@firma.cz")
        self.assertEqual(msg["X-Unsent"], "1")
        self.assertTrue(is_group_emailed(self.drive_date, self.rz.pk))

    @patch("waste_docs.views.ride_document_email.prepare.build_group_email_package")
    def test_prepare_succeeds_without_sender_email(self, mock_build):
        User = get_user_model()
        no_mail = User.objects.create_user("no_mail_view", password="pw", is_superuser=True)
        set_user_role(no_mail, ROLE_ADMIN)
        self.client.force_login(no_mail)
        mock_build.return_value = self.package
        url = reverse("waste_docs:ride_group_email_prepare")
        resp = self.client.post(
            url,
            data='{"date":"2026-06-12","vehicle_rz_id":%d,"recipient_email":"prijemce@example.com"}'
            % self.rz.pk,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        msg = message_from_bytes(b"".join(resp.streaming_content))
        self.assertIsNone(msg["From"])
        self.assertIsNone(msg["Reply-To"])
        self.assertTrue(is_group_emailed(self.drive_date, self.rz.pk))

    def test_prepare_rejects_invalid_email(self):
        url = reverse("waste_docs:ride_group_email_prepare")
        resp = self.client.post(
            url,
            data='{"date":"2026-06-12","vehicle_rz_id":%d,"recipient_email":"not-an-email"}' % self.rz.pk,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_cancel_dispatch(self):
        record_group_dispatch(
            drive_date=self.drive_date,
            vehicle_rz_id=self.rz.pk,
            recipient_email="x@example.com",
            subject="S",
            ride_count=1,
            attachment_count=2,
            user=self.user,
        )
        url = reverse("waste_docs:ride_group_email_cancel")
        resp = self.client.post(
            url,
            data='{"date":"2026-06-12","vehicle_rz_id":%d}' % self.rz.pk,
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(is_group_emailed(self.drive_date, self.rz.pk))


class RideGroupEmailDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_dash_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)
        self.drive_date = date(2026, 6, 13)
        self.rz = VehicleRzCatalog.objects.create(value="6E66666")
        common = dict(
            name=NameCatalog.objects.create(value="Subjekt dash email"),
            ico=IcoCatalog.objects.create(value="77665544"),
            address=AddressCatalog.objects.create(value="Adr dash"),
            waste_type=WasteTypeCatalog.objects.create(code="883344", value="Wdash"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDH"),
            waste_category=WasteCategoryCatalog.objects.create(value="KODH"),
            suffix=SuffixCatalog.objects.create(value="SFXDH"),
            drive_date=self.drive_date,
            created_by=self.user,
            container_number="",
        )
        Pruvodka.objects.create(
            vehicle_rz=self.rz,
            vehicle_rz_snapshot="6E66666",
            ride_group_number=500,
            ride_sequence=1,
            created_at=datetime(2026, 6, 13, 9, 0, tzinfo=dt_timezone.utc),
            **common,
        )

    def test_dashboard_shows_email_button_for_selected_group(self):
        group_key = f"{self.drive_date.isoformat()}::{self.rz.pk}"
        url = reverse("core:dashboard") + f"?date={self.drive_date.isoformat()}&ride_group={group_key}"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "data-dash-ride-email-open")
        self.assertContains(resp, "dash-ride-email-modal")
        self.assertContains(resp, "ride_email_dispatch.js?v=6")
        self.assertContains(resp, "dash-ride-email-save-preset")
        self.assertContains(resp, "dash-ride-email-recipient-preset")

    def test_ride_email_dispatch_js_has_no_django_template_tags(self):
        from django.conf import settings
        from pathlib import Path

        js_path = Path(settings.BASE_DIR) / "core/static/core/js/ride_email_dispatch.js"
        content = js_path.read_text(encoding="utf-8")
        self.assertNotIn("{%", content)
        self.assertTrue(content.lstrip().startswith("(function ()"))


class RideEmailRecipientApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("email_recipient_user", password="pw", is_superuser=True)
        set_user_role(self.user, ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)

    def test_list_recipients_empty(self):
        url = reverse("waste_docs:ride_email_recipients_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["recipients"], [])

    def test_add_and_list_recipient(self):
        add_url = reverse("waste_docs:ride_email_recipient_add")
        resp = self.client.post(
            add_url,
            data='{"email":"Dispetcher@Firma.CZ"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["created"])
        self.assertEqual(data["recipient"]["email"], "dispetcher@firma.cz")
        self.assertEqual(RideEmailRecipient.objects.count(), 1)

        list_resp = self.client.get(reverse("waste_docs:ride_email_recipients_list"))
        self.assertEqual(len(list_resp.json()["recipients"]), 1)

    def test_add_duplicate_is_idempotent(self):
        add_url = reverse("waste_docs:ride_email_recipient_add")
        self.client.post(
            add_url,
            data='{"email":"a@b.cz"}',
            content_type="application/json",
        )
        resp = self.client.post(
            add_url,
            data='{"email":"a@b.cz"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["created"])
        self.assertEqual(RideEmailRecipient.objects.count(), 1)

    def test_add_invalid_email(self):
        add_url = reverse("waste_docs:ride_email_recipient_add")
        resp = self.client.post(
            add_url,
            data='{"email":"not-an-email"}',
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_recipient(self):
        row, _ = add_recipient("delete-me@example.com", user=self.user)
        delete_url = reverse("waste_docs:ride_email_recipient_delete", kwargs={"pk": row.pk})
        resp = self.client.post(delete_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(RideEmailRecipient.objects.count(), 0)

    def test_touch_recipient_used(self):
        row, _ = add_recipient("touch@example.com", user=self.user)
        self.assertIsNone(row.last_used_at)
        touch_recipient_used("touch@example.com")
        row.refresh_from_db()
        self.assertIsNotNone(row.last_used_at)
