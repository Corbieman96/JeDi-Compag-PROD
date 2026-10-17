"""Denní limit a sběr řádků matice požadavku."""

from datetime import date

from django.http import QueryDict
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    ContainerPassport,
    DriverProfile,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from core.models import AppSettings
from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role

from waste_docs.models import SvozTask, SvozYardDriverPlan
from waste_docs.services.svoz_dispatch import assign_driver_for_new_task
from waste_docs.services.svoz_matrix_container_entries import non_empty_container_entries
from waste_docs.services.svoz_matrix_post_collect import collect_pending_svoz_matrix_lines
from waste_docs.services.svoz_request_daily_limit import svoz_subject_has_submitted_today


class SvozMatrixCollectTests(TestCase):
    def setUp(self):
        self.target = date(2031, 7, 1)
        self.name = NameCatalog.objects.create(value="Collect yard")
        self.subject_a = NameSubjectProfile.objects.create(name=self.name, company_name="Collect A")
        self.subject_a.yard_settings.is_collection_yard = True
        self.subject_a.yard_settings.save()
        self.wt_a = WasteTypeCatalog.objects.create(code="COL01", value="A")
        self.wt_b = WasteTypeCatalog.objects.create(code="COL02", value="B")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="VK ok", shortcut="OK", sort_order=0)
        self.vk_orphan = VehicleKindCatalog.objects.create(name="VK no plan", shortcut="NP", sort_order=1)
        self.activity = ActivityCatalog.objects.create(name="Svoz collect")
        self.driver = DriverProfile.objects.create(personal_number="COL-1", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="COLRZ")
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject_a,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk)

        self.pair_ok = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject_a,
            waste_type=self.wt_a,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pair_no_plan = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject_a,
            waste_type=self.wt_b,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk_orphan,
            yard_svoz_activity=self.activity,
        )
        for num, vk in (
            ("C-OK", self.vk),
            ("C-NOPLAN", self.vk_orphan),
            ("215", self.vk),
            ("218", self.vk),
        ):
            ContainerPassport.objects.create(container_number=num, vehicle_kind=vk, color="—")

        self.subject_a.yard_settings.yard_allow_matrix = True
        self.subject_a.yard_settings.save()

    def _login_yard_user(self):
        User = get_user_model()
        yard_user = User.objects.create_user("yard_daily", password="pw")
        set_user_role(yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=yard_user)
        prof.sberny_dvur_subject = self.subject_a
        prof.save(update_fields=["sberny_dvur_subject_id"])
        self.client.force_login(yard_user)
        return yard_user

    def test_mixed_rows_collect_without_plan_blocking_errors(self):
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair_ok.pk), str(self.pair_no_plan.pk)])
        qd[f"containers_{self.pair_ok.pk}"] = "C-OK\n"
        qd[f"containers_{self.pair_no_plan.pk}"] = "C-NOPLAN\n"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject_a,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 2)

    def test_comma_separated_containers_split_to_two_requests(self):
        self.assertEqual(non_empty_container_entries("215, 218"), ["215", "218"])
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair_ok.pk)])
        qd[f"containers_{self.pair_ok.pk}"] = "215, 218"

        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject_a,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 2)
        self.assertEqual(sorted(p.container_numbers for p in pending), ["215", "218"])

    def test_create_task_then_assign_driver_from_plan(self):
        User = get_user_model()
        actor = User.objects.create_user("yard_collect", password="pw")
        task = SvozTask.objects.create(
            subject_profile=self.subject_a,
            created_by=actor,
            waste_type=self.wt_a,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_ok,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="C-OK",
            target_date=self.target,
        )
        assign_driver_for_new_task(task, self.pair_ok, actor=actor)
        task.refresh_from_db()
        self.assertEqual(task.assigned_driver_id, self.driver.pk)
        self.assertEqual(task.assigned_vehicle_rz_id, self.rz.pk)

    def test_svoz_subject_has_submitted_today_after_task_created(self):
        User = get_user_model()
        actor = User.objects.create_user("yard_limit_chk", password="pw")
        self.assertFalse(svoz_subject_has_submitted_today(subject_profile_id=self.subject_a.pk))
        SvozTask.objects.create(
            subject_profile=self.subject_a,
            created_by=actor,
            waste_type=self.wt_a,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_ok,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="C-OK",
            target_date=self.target,
        )
        self.assertTrue(svoz_subject_has_submitted_today(subject_profile_id=self.subject_a.pk))

    def test_svoz_request_post_blocked_after_today_submission(self):
        self._login_yard_user()
        User = get_user_model()
        actor = User.objects.create_user("yard_limit_actor", password="pw")
        SvozTask.objects.create(
            subject_profile=self.subject_a,
            created_by=actor,
            waste_type=self.wt_a,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_ok,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="C-OK",
            target_date=self.target,
        )
        url = reverse("waste_docs:svoz_request")
        r = self.client.post(
            url,
            {
                "pair_pk": [str(self.pair_ok.pk)],
                f"containers_{self.pair_ok.pk}": "215",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dnes jste již odeslali hlášení")

    def test_svoz_request_allows_resubmit_when_daily_limit_disabled(self):
        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])
        self._login_yard_user()
        User = get_user_model()
        actor = User.objects.create_user("yard_limit_off", password="pw")
        SvozTask.objects.create(
            subject_profile=self.subject_a,
            created_by=actor,
            waste_type=self.wt_a,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_ok,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="C-OK",
            target_date=self.target,
        )
        before = SvozTask.objects.filter(subject_profile=self.subject_a).count()
        url = reverse("waste_docs:svoz_request")
        r = self.client.post(
            url,
            {
                "pair_pk": [str(self.pair_ok.pk)],
                f"containers_{self.pair_ok.pk}": "215",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject_a).count(), before + 1)
        settings_obj.svoz_disable_yard_daily_submit_limit = False
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

    def test_collect_allows_same_pair_container_when_enforced(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = True
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        User = get_user_model()
        actor = User.objects.create_user("yard_dup_svoz", password="pw")
        SvozTask.objects.create(
            subject_profile=self.subject_a,
            created_by=actor,
            waste_type=self.wt_a,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair_ok,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="215",
            target_date=self.target,
            status=SvozTask.Status.OPEN,
        )
        qd = QueryDict(mutable=True)
        qd.setlist("pair_pk", [str(self.pair_ok.pk)])
        qd[f"containers_{self.pair_ok.pk}"] = "215"
        pending, errs = collect_pending_svoz_matrix_lines(
            qd.getlist("pair_pk"),
            qd,
            self.subject_a,
            self.target,
        )
        self.assertEqual(errs, [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].container_numbers, "215")
