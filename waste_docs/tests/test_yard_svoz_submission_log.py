"""Log odeslaných řádků matice na /svoz-pozadavek/."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    ContainerPassport,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from core.models import AppSettings
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import SvozTask, YardSvozSubmissionLog
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.yard_svoz_submission_log import (
    LOG_RETENTION_DAYS,
    purge_yard_svoz_submission_logs_older_than,
    record_submission_log_line,
    yard_svoz_submissions_grouped,
)


@override_settings(TIME_ZONE="Europe/Prague")
class YardSvozSubmissionLogServiceTests(TestCase):
    def setUp(self):
        AppSettings._cached_load.cache_clear()
        User = get_user_model()
        self.user_a = User.objects.create_user("yard_log_a", password="pw")
        self.user_b = User.objects.create_user("yard_log_b", password="pw")

        self.name = NameCatalog.objects.create(value="Log yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Log")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()

        for user in (self.user_a, self.user_b):
            set_user_role(user, ROLE_SBERNY_DVUR)
            prof, _ = UserAccessProfile.objects.get_or_create(user=user)
            prof.sberny_dvur_subject = self.subject
            prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt = WasteTypeCatalog.objects.create(code="LOG01", value="Log waste")
        self.suf = SuffixCatalog.objects.create(value="LG")
        self.vk = VehicleKindCatalog.objects.create(name="VkLog", shortcut="LG", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc log")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pline = SvozPendingLine(
            pair=self.pair,
            matrix_display_label="Řádek log",
            yard_contact_note="pozn",
            container_numbers="LOG-100",
        )
        self.target = date(2037, 1, 12)

    def test_record_and_group_today(self):
        record_submission_log_line(
            pline=self.pline,
            subject=self.subject,
            user=self.user_a,
            target_date=self.target,
        )
        groups = yard_svoz_submissions_grouped(subject_profile_id=self.subject.pk)
        self.assertEqual(len(groups["today"]), 1)
        self.assertEqual(groups["today"][0].container_numbers, "LOG-100")
        self.assertEqual(groups["history_by_day"], [])
        self.assertEqual(groups["history_total_count"], 0)

    def test_two_users_same_subject_see_same_log(self):
        record_submission_log_line(
            pline=self.pline,
            subject=self.subject,
            user=self.user_a,
            target_date=self.target,
        )
        groups_a = yard_svoz_submissions_grouped(subject_profile_id=self.subject.pk)
        groups_b = yard_svoz_submissions_grouped(subject_profile_id=self.subject.pk)
        self.assertEqual(groups_a["today"][0].created_by_label, groups_b["today"][0].created_by_label)

    def test_history_excludes_today_from_history_section(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        YardSvozSubmissionLog.objects.create(
            subject_profile=self.subject,
            submission_day=yesterday,
            display_label="Včera",
            waste_type=self.wt,
            suffix=self.suf,
            container_numbers="OLD-1",
            vehicle_kind=self.vk,
            created_by=self.user_a,
            source_waste_suffix_pair=self.pair,
        )
        record_submission_log_line(
            pline=self.pline,
            subject=self.subject,
            user=self.user_a,
            target_date=self.target,
        )
        groups = yard_svoz_submissions_grouped(subject_profile_id=self.subject.pk)
        self.assertEqual(len(groups["today"]), 1)
        self.assertEqual(len(groups["history_by_day"]), 1)
        self.assertEqual(groups["history_by_day"][0][0], yesterday)
        self.assertEqual(groups["history_by_day"][0][1][0].container_numbers, "OLD-1")
        self.assertEqual(groups["history_total_count"], 1)

    def test_purge_old_log_keeps_svoz_task(self):
        old_day = timezone.localdate() - timedelta(days=LOG_RETENTION_DAYS + 1)
        YardSvozSubmissionLog.objects.create(
            subject_profile=self.subject,
            submission_day=old_day,
            display_label="Starý",
            waste_type=self.wt,
            suffix=self.suf,
            container_numbers="OLD-PURGE",
            vehicle_kind=self.vk,
            created_by=self.user_a,
            source_waste_suffix_pair=self.pair,
        )
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.user_a,
            waste_type=self.wt,
            suffix=self.suf,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="TASK-KEEP",
            target_date=self.target,
        )
        deleted = purge_yard_svoz_submission_logs_older_than()
        self.assertEqual(deleted, 1)
        self.assertEqual(SvozTask.objects.count(), 1)
        self.assertEqual(YardSvozSubmissionLog.objects.count(), 0)


@override_settings(TIME_ZONE="Europe/Prague")
class YardSvozSubmissionLogViewTests(TestCase):
    def setUp(self):
        AppSettings._cached_load.cache_clear()
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_log_view", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        self.name = NameCatalog.objects.create(value="View log yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD View Log")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt = WasteTypeCatalog.objects.create(code="LOG02", value="View log waste")
        self.suf = SuffixCatalog.objects.create(value="VL")
        self.vk = VehicleKindCatalog.objects.create(name="VkVL", shortcut="VL", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc view log")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        ContainerPassport.objects.create(
            container_number="VL-100",
            vehicle_kind=self.vk,
            color="—",
        )
        self.client = Client()
        self.client.force_login(self.yard_user)
        self.url = reverse("waste_docs:svoz_request")
        self.target = date(2037, 2, 10)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_post_creates_log_and_shows_today_list(self, mock_target):
        mock_target.return_value = self.target
        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

        r = self.client.post(
            self.url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "VL-100",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(YardSvozSubmissionLog.objects.count(), 1)
        self.assertEqual(SvozTask.objects.count(), 1)

        page = self.client.get(self.url)
        self.assertContains(page, "Dnes odeslané")
        self.assertContains(page, "VL-100")

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_form_appears_before_collapsed_history(self, mock_target):
        mock_target.return_value = self.target
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        YardSvozSubmissionLog.objects.create(
            subject_profile=self.subject,
            submission_day=yesterday,
            display_label="Včera",
            waste_type=self.wt,
            suffix=self.suf,
            container_numbers="HIST-1",
            vehicle_kind=self.vk,
            created_by=self.yard_user,
            source_waste_suffix_pair=self.pair,
        )

        page = self.client.get(self.url)
        content = page.content.decode()
        form_pos = content.find('class="form-grid svoz-matrix-form"')
        history_pos = content.find('id="svoz-submission-history"')
        self.assertGreater(form_pos, -1)
        self.assertGreater(history_pos, -1)
        self.assertLess(form_pos, history_pos)
        self.assertIn(
            '<details class="svoz-log-panel svoz-log-panel--history" id="svoz-submission-history">',
            content,
        )
        self.assertNotIn(
            '<details class="svoz-log-panel svoz-log-panel--history" id="svoz-submission-history" open',
            content,
        )
        self.assertContains(page, "Historie · posledních 7 dní · 1 záznam")
        self.assertContains(page, "HIST-1")

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_second_user_sees_same_submission_list(self, mock_target):
        mock_target.return_value = self.target
        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

        self.client.post(
            self.url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "VL-100",
            },
        )

        User = get_user_model()
        user_b = User.objects.create_user("yard_log_view_b", password="pw")
        set_user_role(user_b, ROLE_SBERNY_DVUR)
        prof_b, _ = UserAccessProfile.objects.get_or_create(user=user_b)
        prof_b.sberny_dvur_subject = self.subject
        prof_b.save(update_fields=["sberny_dvur_subject_id"])

        client_b = Client()
        client_b.force_login(user_b)
        page = client_b.get(self.url)
        self.assertContains(page, "VL-100")

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_today_count_matches_rendered_rows(self, mock_target):
        mock_target.return_value = self.target
        today = timezone.localdate()
        containers = [f"C-{i}" for i in range(1, 8)]
        for num in containers:
            YardSvozSubmissionLog.objects.create(
                subject_profile=self.subject,
                submission_day=today,
                display_label="Řádek test",
                waste_type=self.wt,
                suffix=self.suf,
                container_numbers=num,
                vehicle_kind=self.vk,
                created_by=self.yard_user,
                source_waste_suffix_pair=self.pair,
            )
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Dnes odeslané · 7 požadavků")
        content = page.content.decode()
        today_panel_start = content.find('class="svoz-log-panel svoz-log-panel--today"')
        self.assertGreater(today_panel_start, -1)
        today_section = content[today_panel_start:today_panel_start + 8000]
        self.assertEqual(today_section.count('class="svoz-log-row"'), 7)
        self.assertNotIn("svoz-log-panel__body--scroll", today_section)
        for num in containers:
            self.assertIn(f"k. {num}", today_section)
