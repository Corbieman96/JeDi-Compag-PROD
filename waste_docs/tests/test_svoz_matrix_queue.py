"""Fronta matice SD — okno 11–13, zpracování po 17:00."""

from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka, SvozMatrixQueueEntry, SvozTask
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.svoz_matrix_queue import (
    enqueue_svoz_matrix_lines,
    is_deferred_svoz_matrix_window,
    process_after_for_deferred_submit,
    process_due_svoz_matrix_queue,
)
from waste_docs.services.svoz_request_daily_limit import svoz_subject_has_submitted_today
from waste_docs.svoz_schedule import next_svoz_target_date


def _aware_local(day: date, hour: int, minute: int = 0):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), tz)


@override_settings(TIME_ZONE="Europe/Prague")
class SvozMatrixQueueWindowTests(TestCase):
    def test_deferred_window_11_to_13(self):
        day = date(2036, 6, 16)
        self.assertFalse(is_deferred_svoz_matrix_window(now=_aware_local(day, 10, 59)))
        self.assertTrue(is_deferred_svoz_matrix_window(now=_aware_local(day, 11, 0)))
        self.assertTrue(is_deferred_svoz_matrix_window(now=_aware_local(day, 12, 30)))
        self.assertFalse(is_deferred_svoz_matrix_window(now=_aware_local(day, 13, 0)))

    def test_process_after_is_same_day_17(self):
        now = _aware_local(date(2036, 6, 16), 12, 0)
        after = process_after_for_deferred_submit(now=now)
        local = timezone.localtime(after)
        self.assertEqual(local.date(), date(2036, 6, 16))
        self.assertEqual(local.hour, 17)
        self.assertEqual(local.minute, 0)


@override_settings(TIME_ZONE="Europe/Prague")
class SvozMatrixQueueServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user("queue_sd", password="pw")
        self.submit_day = date(2036, 6, 16)
        self.target = next_svoz_target_date(self.submit_day)

        self.name = NameCatalog.objects.create(value="Queue yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Queue")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="200501", value="Queue waste")
        self.suf = SuffixCatalog.objects.create(value="Q")
        self.vk = VehicleKindCatalog.objects.create(name="VkQ", shortcut="Q", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc queue")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_display_label="Queue row",
        )
        ContainerPassport.objects.create(
            container_number="Q-614",
            vehicle_kind=self.vk,
            color="—",
        )

    def _pline(self, container: str = "Q-614") -> SvozPendingLine:
        return SvozPendingLine(
            pair=self.pair,
            matrix_display_label="Queue row",
            yard_contact_note="",
            container_numbers=container,
        )

    def test_enqueue_creates_queue_not_svoz_task(self):
        noon = _aware_local(self.submit_day, 12, 0)
        n = enqueue_svoz_matrix_lines(
            [self._pline()],
            self.subject,
            self.actor,
            self.target,
            now=noon,
        )
        self.assertEqual(n, 1)
        self.assertEqual(SvozMatrixQueueEntry.objects.count(), 1)
        self.assertEqual(SvozTask.objects.count(), 0)
        entry = SvozMatrixQueueEntry.objects.get()
        self.assertEqual(entry.target_date, self.target)
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PENDING)

    def test_process_after_17_creates_svoz_task(self):
        noon = _aware_local(self.submit_day, 12, 0)
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
        after_17 = _aware_local(self.submit_day, 17, 5)
        stats = process_due_svoz_matrix_queue(now=after_17)
        self.assertEqual(stats.processed, 1)
        self.assertEqual(SvozTask.objects.count(), 1)
        entry = SvozMatrixQueueEntry.objects.get()
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PROCESSED)
        self.assertIsNotNone(entry.result_svoz_task_id)

    def test_process_duplicate_silent_skip(self):
        noon = _aware_local(self.submit_day, 12, 0)
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.actor,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="Q-614",
            target_date=self.target,
        )
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
        after_17 = _aware_local(self.submit_day, 17, 10)
        stats = process_due_svoz_matrix_queue(now=after_17)
        self.assertEqual(stats.skipped_duplicate, 1)
        self.assertEqual(SvozTask.objects.count(), 1)
        entry = SvozMatrixQueueEntry.objects.get()
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.SKIPPED_DUPLICATE)

    def _ride_on_submission_day(self) -> Pruvodka:
        addr = AddressCatalog.objects.create(value="Queue sub day addr")
        return Pruvodka.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="99990001"),
            address=addr,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCQ614"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCQ614"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.submit_day,
            container_number="Q-614",
            created_by=self.actor,
        )

    def test_process_creates_when_ride_on_submission_day(self):
        """Bakov OK: jízda v den hlášení neblokuje úkol na zítřek."""
        self._ride_on_submission_day()
        noon = _aware_local(self.submit_day, 12, 0)
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
        after_17 = _aware_local(self.submit_day, 17, 10)
        stats = process_due_svoz_matrix_queue(now=after_17)
        self.assertEqual(stats.processed, 1)
        self.assertEqual(SvozTask.objects.count(), 1)
        entry = SvozMatrixQueueEntry.objects.get()
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PROCESSED)

    def test_queue_stays_pending_when_ride_created_before_17(self):
        noon = _aware_local(self.submit_day, 12, 0)
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
        entry = SvozMatrixQueueEntry.objects.get()
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PENDING)
        self._ride_on_submission_day()
        entry.refresh_from_db()
        self.assertEqual(entry.status, SvozMatrixQueueEntry.Status.PENDING)

    def test_process_idempotent_second_run_no_op(self):
        noon = _aware_local(self.submit_day, 12, 0)
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
        after_17 = _aware_local(self.submit_day, 17, 5)
        process_due_svoz_matrix_queue(now=after_17)
        stats2 = process_due_svoz_matrix_queue(now=after_17)
        self.assertEqual(stats2.processed, 0)
        self.assertEqual(SvozTask.objects.count(), 1)

    def test_daily_limit_counts_queue_submission(self):
        noon = _aware_local(self.submit_day, 12, 0)
        with patch("django.utils.timezone.now", return_value=noon):
            enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, self.target, now=noon)
            self.assertTrue(
                svoz_subject_has_submitted_today(subject_profile_id=self.subject.pk, now=noon)
            )

    def test_target_date_frozen_at_enqueue(self):
        noon = _aware_local(self.submit_day, 12, 0)
        frozen_target = date(2036, 6, 18)
        enqueue_svoz_matrix_lines([self._pline()], self.subject, self.actor, frozen_target, now=noon)
        after_17 = _aware_local(self.submit_day, 17, 5)
        process_due_svoz_matrix_queue(now=after_17)
        task = SvozTask.objects.get()
        self.assertEqual(task.target_date, frozen_target)


@override_settings(TIME_ZONE="Europe/Prague")
class SvozMatrixQueueViewIntegrationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_queue", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        prof.sberny_dvur_subject = None
        prof.save()

        self.submit_day = date(2036, 6, 17)
        self.target = next_svoz_target_date(self.submit_day)

        self.name = NameCatalog.objects.create(value="View queue yard")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name, company_name="SD View Queue",
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()

        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt = WasteTypeCatalog.objects.create(code="200502", value="View Q waste")
        self.suf = SuffixCatalog.objects.create(value="VQ")
        self.vk = VehicleKindCatalog.objects.create(name="VkVQ", shortcut="VQ", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc view queue")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        ContainerPassport.objects.create(
            container_number="VQ-100",
            vehicle_kind=self.vk,
            color="—",
        )
        self.client = Client()
        self.client.force_login(self.yard_user)
        self.url = reverse("waste_docs:svoz_request")

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_post_creates_svoz_task_immediately(self, mock_target):
        mock_target.return_value = self.target
        from core.models import AppSettings

        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

        r = self.client.post(
            self.url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "VQ-100",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(SvozMatrixQueueEntry.objects.count(), 0)
        self.assertEqual(SvozTask.objects.count(), 1)
