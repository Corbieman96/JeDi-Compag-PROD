"""Deduplikace požadavku svozu na cílový den při odeslání matice."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from core.models import AppSettings
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role

from waste_docs.models import Pruvodka, SvozTask
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine, collect_pending_svoz_matrix_lines
from waste_docs.services.svoz_task_submit import submit_svoz_line_if_allowed


class SvozTaskSubmitDedupTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user("svoz_dedup_user", password="pw")
        self.target = date(2034, 8, 15)
        self.yesterday = self.target - timedelta(days=1)

        self.name = NameCatalog.objects.create(value="Dedup yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Dedup")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="DED01", value="Dedup waste")
        self.wt_b = WasteTypeCatalog.objects.create(code="DED02", value="Dedup waste B")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Hak dedup", shortcut="HD", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz dedup")

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pair_b = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_b,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        ContainerPassport.objects.create(container_number="D-100", vehicle_kind=self.vk, color="—")

        self.yard_user = User.objects.create_user("yard_dedup", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

    def _pline(self, container: str, pair=None) -> SvozPendingLine:
        pair = pair or self.pair
        return SvozPendingLine(
            pair=pair,
            matrix_display_label="",
            yard_contact_note="",
            container_numbers=container,
        )

    def test_skips_duplicate_on_same_target_date(self):
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.target,
            status=SvozTask.Status.OPEN,
        )
        result = submit_svoz_line_if_allowed(
            self._pline("D-100"), self.subject, self.actor, self.target,
        )
        self.assertFalse(result.created)
        self.assertTrue(result.skipped_duplicate)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)

    def test_creates_new_task_when_only_yesterday_open(self):
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.yesterday,
            status=SvozTask.Status.OPEN,
        )
        result = submit_svoz_line_if_allowed(
            self._pline("D-100"), self.subject, self.actor, self.target,
        )
        self.assertTrue(result.created)
        self.assertFalse(result.skipped_duplicate)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 2)
        self.assertEqual(
            SvozTask.objects.filter(target_date=self.target, container_numbers="D-100").count(),
            1,
        )

    def test_creates_after_done_when_no_active_ride_on_target(self):
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.target,
            status=SvozTask.Status.DONE,
        )
        result = submit_svoz_line_if_allowed(
            self._pline("D-100"), self.subject, self.actor, self.target,
        )
        self.assertTrue(result.created)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 2)

    def test_skips_when_done_task_with_pruvodka_on_target(self):
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="616",
            target_date=self.target,
            status=SvozTask.Status.DONE,
        )
        ico = IcoCatalog.objects.create(value="61600001")
        rz = VehicleRzCatalog.objects.create(value="616RZ")
        VehicleRzProfile.objects.create(rz=rz)
        driver = DriverProfile.objects.create(personal_number="616-D", last_name="Sever")
        addr = AddressCatalog.objects.create(value="Sever 1")
        ride = Pruvodka.objects.create(
            name=self.name,
            ico=ico,
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC616"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC616"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.target,
            vehicle_rz=rz,
            driver=driver,
            created_by=self.actor,
            container_number="616",
        )
        task.resolved_pruvodka = ride
        task.save(update_fields=["resolved_pruvodka"])

        result = submit_svoz_line_if_allowed(
            self._pline("616"), self.subject, self.actor, self.target,
        )
        self.assertFalse(result.created)
        self.assertTrue(result.skipped_duplicate)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)

    def test_creates_when_done_and_active_ride_on_target(self):
        """Jízda na cílový den blokuje druhé hlášení stejného kontejneru."""
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="616",
            target_date=self.target - timedelta(days=1),
            status=SvozTask.Status.DONE,
        )
        ico = IcoCatalog.objects.create(value="61600001")
        rz = VehicleRzCatalog.objects.create(value="616RZ")
        VehicleRzProfile.objects.create(rz=rz)
        driver = DriverProfile.objects.create(personal_number="616-D", last_name="Sever")
        addr = AddressCatalog.objects.create(value="Sever 1")
        ride = Pruvodka.objects.create(
            name=self.name,
            ico=ico,
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC616"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC616"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.target,
            vehicle_rz=rz,
            driver=driver,
            created_by=self.actor,
            container_number="616",
        )
        task.resolved_pruvodka = ride
        task.save(update_fields=["resolved_pruvodka"])

        result = submit_svoz_line_if_allowed(
            self._pline("616"), self.subject, self.actor, self.target,
        )
        self.assertFalse(result.created)
        self.assertTrue(result.skipped_duplicate)

    def test_skips_when_active_ride_on_target_without_open_task(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = False
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])

        ico = IcoCatalog.objects.create(value="61600002")
        rz = VehicleRzCatalog.objects.create(value="616RZ2")
        VehicleRzProfile.objects.create(rz=rz)
        driver = DriverProfile.objects.create(personal_number="616-D2", last_name="Sever2")
        addr = AddressCatalog.objects.create(value="Sever 2")
        Pruvodka.objects.create(
            name=self.name,
            ico=ico,
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC616B"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC616B"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.target,
            vehicle_rz=rz,
            driver=driver,
            created_by=self.actor,
            container_number="D-100",
        )

        result = submit_svoz_line_if_allowed(
            self._pline("D-100"), self.subject, self.actor, self.target,
        )
        self.assertFalse(result.created)
        self.assertTrue(result.skipped_duplicate)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 0)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_post_skips_duplicate_silently(self, mock_target):
        mock_target.return_value = self.target
        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.target,
            status=SvozTask.Status.OPEN,
        )
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "D-100",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)
        self.assertEqual(Pruvodka.objects.count(), 0)

    def test_collect_blocks_when_active_ride_on_target(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = True
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        ico = IcoCatalog.objects.create(value="61600003")
        rz = VehicleRzCatalog.objects.create(value="616RZ3")
        VehicleRzProfile.objects.create(rz=rz)
        driver = DriverProfile.objects.create(personal_number="616-D3", last_name="Sever3")
        addr = AddressCatalog.objects.create(value="Sever 3")
        Pruvodka.objects.create(
            name=self.name,
            ico=ico,
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WC616C"),
            waste_category=WasteCategoryCatalog.objects.create(value="KC616C"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.target,
            vehicle_rz=rz,
            driver=driver,
            created_by=self.actor,
            container_number="D-100",
        )
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "D-100"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(pending, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("D-100", errs[0])

    def test_collect_rejects_duplicate_container_across_pairs_in_one_submit(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = True
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk), str(self.pair_b.pk)])
        qd[f"containers_{self.pair.pk}"] = "D-100"
        qd[f"containers_{self.pair_b.pk}"] = "D-100"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(errs), 1)
        self.assertIn("D-100", errs[0])

    def test_collect_allows_same_pair_container_on_target_date(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = True
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.target,
            status=SvozTask.Status.OPEN,
        )
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair.pk)])
        qd[f"containers_{self.pair.pk}"] = "D-100"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 1)

    def test_collect_blocks_cross_pair_same_container_on_target_date(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = True
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="D-100",
            target_date=self.target,
            status=SvozTask.Status.OPEN,
        )
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair_b.pk)])
        qd[f"containers_{self.pair_b.pk}"] = "D-100"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject,
            self.target,
        )
        self.assertEqual(pending, [])
        self.assertEqual(len(errs), 1)
        self.assertIn("D-100", errs[0])
