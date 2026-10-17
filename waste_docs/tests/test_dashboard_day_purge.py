from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
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
from users.constants import ROLE_ADMIN, ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.models import PrintFileMark, Pruvodka
from waste_docs.services.dashboard_day_purge import purge_day_generated_artifacts
from waste_docs.services.dashboard_media_purge import purge_all_generated_artifacts
from waste_docs.services.manual_print_marks import file_row_key, mark_row_printed


class DashboardDayPurgeServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("purge_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.ride_date = date(2027, 5, 20)
        self.rz = VehicleRzCatalog.objects.create(value="1P99999")
        name = NameCatalog.objects.create(value="Subjekt purge test")
        self.ride = Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="99887766"),
            address=AddressCatalog.objects.create(value="Adr purge"),
            waste_type=WasteTypeCatalog.objects.create(code="990099", value="Wpurge"),
            waste_code=WasteCodeCatalog.objects.create(value="WCPG"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOPG"),
            suffix=SuffixCatalog.objects.create(value="SFXPG"),
            drive_date=self.ride_date,
            vehicle_rz=self.rz,
            container_number="",
            created_by=self.admin,
        )

    def _setup_media_files(self, media: Path) -> None:
        pruvodka_rel = "pruvodky/purge_test.xlsx"
        zpo_rel = "pruvodky/zpo_instance/1_test.xlsx"
        protocol_rel = "protokoly/protokol_test.xlsx"
        (media / "pruvodky").mkdir(parents=True, exist_ok=True)
        (media / "pruvodky" / "zpo_instance").mkdir(parents=True, exist_ok=True)
        (media / "protokoly").mkdir(parents=True, exist_ok=True)
        (media / "print_cache" / "pruvodky").mkdir(parents=True, exist_ok=True)
        (media / pruvodka_rel).write_bytes(b"xlsx")
        (media / zpo_rel).write_bytes(b"zpo")
        (media / protocol_rel).write_bytes(b"proto")
        (media / "print_cache" / f"{pruvodka_rel}.pdf").write_bytes(b"pdf")
        self.ride.generated_file.name = pruvodka_rel
        self.ride.zpo_instance_file.name = zpo_rel
        self.ride.status = Pruvodka.Status.GENERATED
        self.ride.save(update_fields=("generated_file", "zpo_instance_file", "status"))
        mark_row_printed(
            self.admin,
            self.ride_date,
            file_row_key(kind="xlsx", media_rel=pruvodka_rel),
        )

    def test_purge_deletes_files_and_resets_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            with override_settings(MEDIA_ROOT=media):
                self._setup_media_files(media)
                result = purge_day_generated_artifacts(self.ride_date, self.admin)
                self.ride.refresh_from_db()

            self.assertEqual(result.pruvodky, 1)
            self.assertEqual(result.zpo, 1)
            self.assertGreaterEqual(result.print_cache, 1)
            self.assertEqual(result.print_marks, 1)
            self.assertEqual(self.ride.status, Pruvodka.Status.RECORDED)
            self.assertFalse(self.ride.generated_file.name)
            self.assertFalse(self.ride.zpo_instance_file.name)
            self.assertFalse((media / "pruvodky" / "purge_test.xlsx").exists())
            self.assertFalse((media / "pruvodky" / "zpo_instance" / "1_test.xlsx").exists())
            self.assertFalse(PrintFileMark.objects.filter(drive_date=self.ride_date).exists())


class DashboardDayPurgeViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("purge_view_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.dispecer = User.objects.create_user("purge_view_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.ride_date = date(2027, 5, 21)
        name = NameCatalog.objects.create(value="Subjekt purge view")
        self.ride = Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="88776655"),
            address=AddressCatalog.objects.create(value="Adr purge view"),
            waste_type=WasteTypeCatalog.objects.create(code="990098", value="Wpgv"),
            waste_code=WasteCodeCatalog.objects.create(value="WCPV"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOPV"),
            suffix=SuffixCatalog.objects.create(value="SFXPV"),
            drive_date=self.ride_date,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P88888"),
            container_number="",
            created_by=self.admin,
        )

    def test_admin_can_purge_via_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            rel = "pruvodky/view_purge.xlsx"
            (media / "pruvodky").mkdir(parents=True)
            (media / rel).write_bytes(b"xlsx")
            with override_settings(MEDIA_ROOT=media):
                self.ride.generated_file.name = rel
                self.ride.status = Pruvodka.Status.GENERATED
                self.ride.save(update_fields=("generated_file", "status"))

                client = Client()
                client.force_login(self.admin)
                url = reverse("waste_docs:dashboard_day_purge")
                response = client.post(url, {"date": self.ride_date.isoformat()})
                self.ride.refresh_from_db()

            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.ride.status, Pruvodka.Status.RECORDED)
            self.assertFalse(self.ride.generated_file.name)

    def test_dispecer_gets_404(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:dashboard_day_purge")
        response = client.post(url, {"date": self.ride_date.isoformat()})
        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_trash_icon_for_admin_only(self):
        admin_client = Client()
        admin_client.force_login(self.admin)
        disp_client = Client()
        disp_client.force_login(self.dispecer)

        dash_url = reverse("core:dashboard") + f"?date={self.ride_date.isoformat()}"
        admin_resp = admin_client.get(dash_url)
        disp_resp = disp_client.get(dash_url)

        self.assertEqual(admin_resp.status_code, 200)
        self.assertContains(admin_resp, "purge-generated")
        self.assertContains(admin_resp, "dash-panel__icon-btn--danger")
        self.assertEqual(disp_resp.status_code, 200)
        self.assertNotContains(disp_resp, "purge-generated")


class DashboardMediaPurgeAllServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("purge_all_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.date_a = date(2027, 6, 18)
        self.date_b = date(2027, 6, 19)
        name = NameCatalog.objects.create(value="Subjekt purge all")
        self.ride_a = Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="11223344"),
            address=AddressCatalog.objects.create(value="Adr A"),
            waste_type=WasteTypeCatalog.objects.create(code="990088", value="Wa"),
            waste_code=WasteCodeCatalog.objects.create(value="WCA"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOA"),
            suffix=SuffixCatalog.objects.create(value="SFXA"),
            drive_date=self.date_a,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P11111"),
            container_number="",
            created_by=self.admin,
        )
        self.ride_b = Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="11223345"),
            address=AddressCatalog.objects.create(value="Adr B"),
            waste_type=WasteTypeCatalog.objects.create(code="990087", value="Wb"),
            waste_code=WasteCodeCatalog.objects.create(value="WCB"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOB"),
            suffix=SuffixCatalog.objects.create(value="SFXB"),
            drive_date=self.date_b,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P22222"),
            container_number="",
            created_by=self.admin,
        )

    def test_purge_all_deletes_every_directory_and_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            rel_a = "pruvodky/day_a.xlsx"
            rel_b = "pruvodky/day_b.xlsx"
            zpo_rel = "pruvodky/zpo_instance/99_orphan.xlsx"
            (media / "pruvodky").mkdir(parents=True)
            (media / "pruvodky" / "zpo_instance").mkdir(parents=True)
            (media / "protokoly").mkdir(parents=True)
            (media / "print_cache" / "bulk_merged").mkdir(parents=True)
            (media / rel_a).write_bytes(b"a")
            (media / rel_b).write_bytes(b"b")
            (media / zpo_rel).write_bytes(b"z")
            (media / "protokoly" / "protokol_orphan.xlsx").write_bytes(b"p")
            (media / "print_cache" / "bulk_merged" / "merged.pdf").write_bytes(b"m")
            with override_settings(MEDIA_ROOT=media):
                self.ride_a.generated_file.name = rel_a
                self.ride_a.zpo_instance_file.name = zpo_rel
                self.ride_a.status = Pruvodka.Status.GENERATED
                self.ride_a.save(update_fields=("generated_file", "zpo_instance_file", "status"))
                self.ride_b.generated_file.name = rel_b
                self.ride_b.status = Pruvodka.Status.GENERATED
                self.ride_b.save(update_fields=("generated_file", "status"))
                mark_row_printed(self.admin, self.date_a, file_row_key(kind="xlsx", media_rel=rel_a))
                mark_row_printed(self.admin, self.date_b, file_row_key(kind="xlsx", media_rel=rel_b))

                result = purge_all_generated_artifacts()
                self.ride_a.refresh_from_db()
                self.ride_b.refresh_from_db()

            self.assertEqual(result.pruvodky, 2)
            self.assertEqual(result.zpo, 1)
            self.assertEqual(result.protokoly, 1)
            self.assertEqual(result.print_cache, 1)
            self.assertEqual(result.print_marks, 2)
            self.assertEqual(result.db_rides, 2)
            self.assertEqual(self.ride_a.status, Pruvodka.Status.RECORDED)
            self.assertEqual(self.ride_b.status, Pruvodka.Status.RECORDED)
            self.assertFalse(self.ride_a.generated_file.name)
            self.assertFalse(self.ride_a.zpo_instance_file.name)
            self.assertFalse(self.ride_b.generated_file.name)
            self.assertFalse(list((media / "pruvodky").glob("*.xlsx")))
            self.assertFalse(list((media / "pruvodky" / "zpo_instance").glob("*")))
            self.assertFalse(list((media / "protokoly").glob("*")))
            self.assertFalse(any(p.is_file() for p in (media / "print_cache").rglob("*")))
            self.assertFalse(PrintFileMark.objects.exists())


class DashboardMediaPurgeAllViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("purge_all_view_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.dispecer = User.objects.create_user("purge_all_view_disp", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.ride_date = date(2027, 6, 18)
        name = NameCatalog.objects.create(value="Subjekt purge all view")
        Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="55443322"),
            address=AddressCatalog.objects.create(value="Adr view"),
            waste_type=WasteTypeCatalog.objects.create(code="990086", value="Wv"),
            waste_code=WasteCodeCatalog.objects.create(value="WCV"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOV"),
            suffix=SuffixCatalog.objects.create(value="SFXV"),
            drive_date=self.ride_date,
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P33333"),
            container_number="",
            created_by=self.admin,
        )

    def test_admin_can_purge_all_via_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp)
            (media / "protokoly").mkdir(parents=True)
            (media / "protokoly" / "leftover.xlsx").write_bytes(b"x")
            with override_settings(MEDIA_ROOT=media):
                client = Client()
                client.force_login(self.admin)
                url = reverse("waste_docs:dashboard_media_purge_all")
                response = client.post(url, {"date": self.ride_date.isoformat()})

            self.assertEqual(response.status_code, 302)
            self.assertFalse((media / "protokoly" / "leftover.xlsx").exists())

    def test_dispecer_gets_404(self):
        client = Client()
        client.force_login(self.dispecer)
        url = reverse("waste_docs:dashboard_media_purge_all")
        response = client.post(url, {"date": self.ride_date.isoformat()})
        self.assertEqual(response.status_code, 404)

    def test_dashboard_shows_purge_all_for_admin_only(self):
        admin_client = Client()
        admin_client.force_login(self.admin)
        disp_client = Client()
        disp_client.force_login(self.dispecer)
        dash_url = reverse("core:dashboard") + f"?date={self.ride_date.isoformat()}"
        admin_resp = admin_client.get(dash_url)
        disp_resp = disp_client.get(dash_url)
        self.assertContains(admin_resp, "purge-generated-all")
        self.assertNotContains(disp_resp, "purge-generated-all")
