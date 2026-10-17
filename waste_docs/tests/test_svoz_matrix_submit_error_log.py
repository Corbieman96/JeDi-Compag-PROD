"""Chybový log odeslání matice — jeden log na dvůr, modal dispečera."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from users.constants import ROLE_ADMIN, ROLE_DISPECER, ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import YardSvozSubmissionLog, YardSvozSubmitErrorLog
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine
from waste_docs.services.svoz_matrix_submit_error_log import (
    acknowledge_unread_for_subject,
    delete_row,
    record_error_messages,
    rows_for_subject,
)
from waste_docs.services.svoz_matrix_submit_error_log.group_days import format_day_label
from waste_docs.services.svoz_matrix_submit_error_log.query import dispatcher_alert_unread_count
from waste_docs.services.yard_svoz_submission_log import record_submission_log_line
from waste_docs.services.yard_svoz_submission_result import (
    RESULT_UNASSIGNED,
    result_summary_for_hazard,
    result_summary_for_svoz_task,
)


@override_settings(TIME_ZONE="Europe/Prague")
class YardSvozSubmitErrorLogTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_err_log", password="pw")
        self.disp = User.objects.create_user("disp_err_log", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        set_user_role(self.disp, ROLE_DISPECER)

        self.name = NameCatalog.objects.create(value="Err yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Err Log")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()

        self.name2 = NameCatalog.objects.create(value="Err yard 2")
        self.subject2 = NameSubjectProfile.objects.create(name=self.name2, company_name="SD Err Other")
        self.subject2.yard_settings.is_collection_yard = True
        self.subject2.yard_settings.save()

        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt = WasteTypeCatalog.objects.create(code="ER01", value="Err waste")
        self.suf = SuffixCatalog.objects.create(value="ER")
        self.vk = VehicleKindCatalog.objects.create(name="VkErr", shortcut="ER", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svc err")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.client = Client()
        self.url = reverse("waste_docs:svoz_request")
        self.target = date(2037, 4, 1)

    def test_record_is_per_yard(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["chyba A"],
        )
        record_error_messages(
            subject=self.subject2,
            user=self.yard_user,
            messages=["chyba B"],
        )
        own = rows_for_subject(subject_profile_id=self.subject.pk)
        other = rows_for_subject(subject_profile_id=self.subject2.pk)
        self.assertEqual([r.message for r in own], ["chyba A"])
        self.assertEqual([r.message for r in other], ["chyba B"])

    @patch("waste_docs.views.dispatch.svoz_request.svoz_subject_has_submitted_today", return_value=False)
    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_invalid_container_writes_error_not_success_log(self, mock_target, _submitted):
        mock_target.return_value = self.target

        self.client.force_login(self.yard_user)
        response = self.client.post(
            self.url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "NEEXISTUJE-999",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(YardSvozSubmissionLog.objects.count(), 0)
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.subject_profile_id, self.subject.pk)
        self.assertIn("NEEXISTUJE-999", entry.message)
        self.assertContains(response, "Chyby odeslání")
        self.assertContains(response, "NEEXISTUJE-999")

    def test_dispatcher_sees_alert_and_can_delete_row(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["kontejner X není v číselníku pasportů"],
        )
        self.client.force_login(self.disp)
        dash = self.client.get(reverse("core:dashboard"))
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "Chyby SD")
        # Text chyby je v Log SD / modal partial — na dashboardu jen badge.
        self.assertContains(dash, "Chyby SD (1)")

        pk = YardSvozSubmitErrorLog.objects.get().pk
        log_page = self.client.get(
            reverse("waste_docs:svoz_submit_error_log"),
            {"subject": self.subject.pk},
        )
        self.assertContains(log_page, "kontejner X není v číselníku pasportů")

        deleted = self.client.post(
            reverse("waste_docs:svoz_submit_error_log_delete_row", args=[pk]),
            {"date": "2037-04-01"},
        )
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(YardSvozSubmitErrorLog.objects.filter(pk=pk).exists())

    def test_dispatcher_and_admin_see_nav_page_yard_gets_404(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["kontejner X není v číselníku pasportů"],
        )
        log_url = reverse("waste_docs:svoz_submit_error_log")

        self.client.force_login(self.disp)
        page = self.client.get(log_url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Log SD")
        self.assertContains(page, "Vyberte sběrný dvůr")
        self.assertNotContains(page, "kontejner X není v číselníku pasportů")

        loaded = self.client.get(log_url, {"subject": self.subject.pk})
        self.assertContains(loaded, "kontejner X není v číselníku pasportů")

        User = get_user_model()
        admin = User.objects.create_user("admin_err_log", password="pw")
        set_user_role(admin, ROLE_ADMIN)
        self.client.force_login(admin)
        admin_page = self.client.get(log_url)
        self.assertEqual(admin_page.status_code, 200)
        self.assertContains(admin_page, "Log SD")

        self.client.force_login(self.yard_user)
        yard_page = self.client.get(log_url)
        self.assertEqual(yard_page.status_code, 404)

        pk = YardSvozSubmitErrorLog.objects.get().pk
        self.client.force_login(self.disp)
        deleted = self.client.post(
            reverse("waste_docs:svoz_submit_error_log_delete_row", args=[pk]),
            {"next": "log"},
        )
        self.assertEqual(deleted.status_code, 302)
        self.assertEqual(deleted.url, log_url)
        self.assertFalse(YardSvozSubmitErrorLog.objects.filter(pk=pk).exists())

    @patch("waste_docs.services.svoz_matrix_submit_error_log.manage.reclaim_sqlite_space_after_delete")
    def test_delete_row_hard_deletes_from_db(self, mock_reclaim):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["řádek k trvalému smazání"],
        )
        pk = YardSvozSubmitErrorLog.objects.get().pk
        self.assertTrue(delete_row(pk=pk))
        self.assertFalse(YardSvozSubmitErrorLog.objects.filter(pk=pk).exists())
        mock_reclaim.assert_called_once()

    def test_yard_user_cannot_delete_row(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["chyba C"],
        )
        pk = YardSvozSubmitErrorLog.objects.get().pk
        self.client.force_login(self.yard_user)
        response = self.client.post(
            reverse("waste_docs:svoz_submit_error_log_delete_row", args=[pk]),
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(YardSvozSubmitErrorLog.objects.filter(pk=pk).exists())

    def test_success_same_day_clears_dispatcher_alert(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["špatné číslo kontejneru"],
        )
        self.assertEqual(dispatcher_alert_unread_count(), 1)
        self.client.force_login(self.disp)
        dash = self.client.get(reverse("core:dashboard"))
        self.assertContains(dash, "Chyby SD")

        pline = SvozPendingLine(
            pair=self.pair,
            matrix_display_label="Řádek",
            yard_contact_note="",
            container_numbers="OK-1",
        )
        record_submission_log_line(
            pline=pline,
            subject=self.subject,
            user=self.yard_user,
            target_date=self.target,
        )
        acknowledge_unread_for_subject(
            subject_profile_id=self.subject.pk,
            user=self.yard_user,
        )
        self.assertEqual(dispatcher_alert_unread_count(), 0)
        dash2 = self.client.get(reverse("core:dashboard"))
        self.assertNotContains(dash2, "Chyby SD (")
        self.assertTrue(YardSvozSubmitErrorLog.objects.filter(subject_profile=self.subject).exists())

    def test_live_validate_unknown_container_writes_log_without_alert(self):
        self.client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_matrix_validate_container")
        first = self.client.get(url, {"pair_pk": self.pair.pk, "containers": "600"})
        self.assertEqual(first.status_code, 200)
        self.assertFalse(first.json().get("ok"))
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.LIVE)
        self.assertEqual(entry.container_numbers, "600")
        self.assertEqual(dispatcher_alert_unread_count(), 0)

        second = self.client.get(url, {"pair_pk": self.pair.pk, "containers": "600"})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)

        self.client.force_login(self.disp)
        page = self.client.get(reverse("waste_docs:svoz_submit_error_log"), {"subject": self.subject.pk})
        self.assertContains(page, "Kontrola při psaní")
        self.assertContains(page, "600")

    def test_live_confirm_accepted_writes_log_with_confirmer(self):
        self.yard_user.first_name = "Marie"
        self.yard_user.last_name = "Nová"
        self.yard_user.save(update_fields=["first_name", "last_name"])
        self.client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_matrix_validate_container")
        response = self.client.get(
            url,
            {
                "pair_pk": self.pair.pk,
                "containers": "999-xyz",
                "confirm_accepted": "1",
                "accepted_number": "999-xyz",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("ok"))
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.LIVE)
        self.assertEqual(entry.container_numbers, "999-xyz")
        self.assertIn("Potvrzeno číslo mimo číselník 999-xyz", entry.message)
        self.assertIn("Marie Nová", entry.message)
        self.assertEqual(dispatcher_alert_unread_count(), 0)

        again = self.client.get(
            url,
            {
                "pair_pk": self.pair.pk,
                "containers": "999-xyz",
                "confirm_accepted": "1",
                "accepted_number": "999-xyz",
            },
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)

    def test_sent_line_shows_result_on_log_page(self):
        pline = SvozPendingLine(
            pair=self.pair,
            matrix_display_label="Řádek",
            yard_contact_note="",
            container_numbers="OK-1",
        )
        record_submission_log_line(
            pline=pline,
            subject=self.subject,
            user=self.yard_user,
            target_date=self.target,
            result_summary=RESULT_UNASSIGNED,
        )
        self.client.force_login(self.disp)
        page = self.client.get(reverse("waste_docs:svoz_submit_error_log"), {"subject": self.subject.pk})
        self.assertContains(page, "Odesláno")
        self.assertContains(page, "Požadavek na svoz bez řidiče")
        self.assertContains(page, "koncovka ER")

    def test_result_summary_helpers(self):
        class _Task:
            assigned_driver = None
            assigned_vehicle_rz = None
            resolved_pruvodka_id = None

        self.assertEqual(result_summary_for_svoz_task(task=_Task()), RESULT_UNASSIGNED)
        self.assertEqual(result_summary_for_hazard(), "Nebezpečný odpad — fronta dispečera")

        class _Driver:
            first_name = "Jan"
            last_name = "Novák"

        class _Rz:
            value = "1A2 3456"

        class _Assigned:
            assigned_driver = _Driver()
            assigned_vehicle_rz = _Rz()
            resolved_pruvodka_id = 1

        text = result_summary_for_svoz_task(task=_Assigned())
        self.assertIn("Jan Novák", text)
        self.assertIn("1A2 3456", text)
        self.assertIn("jízda založena", text)

    def test_log_page_loads_only_selected_yard(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["chyba A"],
        )
        record_error_messages(
            subject=self.subject2,
            user=self.yard_user,
            messages=["chyba B"],
        )
        log_url = reverse("waste_docs:svoz_submit_error_log")
        self.client.force_login(self.disp)
        blank = self.client.get(log_url)
        self.assertContains(blank, "Vyberte sběrný dvůr")
        self.assertContains(blank, "Načíst")
        self.assertNotContains(blank, "chyba A")
        self.assertNotContains(blank, "chyba B")

        loaded = self.client.get(log_url, {"subject": self.subject.pk})
        self.assertContains(loaded, "chyba A")
        self.assertNotContains(loaded, "chyba B")
        self.assertContains(loaded, "SD Err Log")

    def test_yard_login_writes_who_and_when_dispatcher_does_not(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "yard_err_log", "password": "pw"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(YardSvozSubmitErrorLog.objects.count(), 1)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.LOGIN)
        self.assertEqual(entry.created_by_id, self.yard_user.pk)
        self.assertEqual(entry.subject_profile_id, self.subject.pk)
        self.assertIn("Přihlášení", entry.message)
        self.assertIsNotNone(entry.created_at)
        self.assertEqual(dispatcher_alert_unread_count(), 0)

        viewer = Client()
        viewer.force_login(self.disp)
        page = viewer.get(
            reverse("waste_docs:svoz_submit_error_log"),
            {"subject": self.subject.pk},
        )
        self.assertContains(page, "Přihlášení")
        self.assertContains(page, "yard_err_log")
        self.assertNotContains(page, "Přihlášení do sběrného dvora")

        dash = viewer.get(reverse("core:dashboard"))
        self.assertEqual(dash.status_code, 200)
        self.assertNotContains(dash, "Přihlášení")
        self.assertNotContains(dash, "Log chyb SD")
        self.assertNotContains(dash, "Chyby SD")

        yard_matrix = self.client.get(reverse("waste_docs:svoz_request"))
        self.assertEqual(yard_matrix.status_code, 200)
        self.assertEqual(len(yard_matrix.context["submit_error_log_rows"]), 0)
        self.assertNotContains(yard_matrix, "Přihlášení do sběrného dvora")

        other = Client()
        disp_login = other.post(
            reverse("login"),
            {"username": "disp_err_log", "password": "pw"},
        )
        self.assertEqual(disp_login.status_code, 302)
        self.assertEqual(
            YardSvozSubmitErrorLog.objects.filter(source=YardSvozSubmitErrorLog.Source.LOGIN).count(),
            1,
        )

    def _backdate_error(self, entry, *, days_ago: int):
        from django.utils import timezone

        when = timezone.now() - timedelta(days=days_ago)
        entry.created_at = when
        entry.submission_day = timezone.localdate(when)
        entry.save(update_fields=["created_at", "submission_day"])

    def _backdate_sent(self, entry, *, days_ago: int):
        from django.utils import timezone

        when = timezone.now() - timedelta(days=days_ago)
        entry.submitted_at = when
        entry.submission_day = timezone.localdate(when)
        entry.save(update_fields=["submitted_at", "submission_day"])

    def _day_label(self, day):
        return format_day_label(day)

    def test_log_page_groups_rows_by_day(self):
        from django.utils import timezone

        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["dnes chyba"],
        )
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["včera chyba"],
        )
        yesterday_row = YardSvozSubmitErrorLog.objects.get(message="včera chyba")
        self._backdate_error(yesterday_row, days_ago=1)
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)

        self.client.force_login(self.disp)
        page = self.client.get(
            reverse("waste_docs:svoz_submit_error_log"),
            {"subject": self.subject.pk},
        )
        self.assertContains(page, self._day_label(today))
        self.assertContains(page, self._day_label(yesterday))
        self.assertContains(page, "Smazat vybrané")
        self.assertContains(page, 'name="day"')
        self.assertContains(page, 'name="error"')
        self.assertNotContains(page, "Smazat log chyb")

    @patch("waste_docs.services.svoz_matrix_submit_error_log.delete_selected.reclaim_sqlite_space_after_delete")
    def test_delete_selected_row_keeps_other_day(self, mock_reclaim):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["dnes chyba"],
        )
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["včera chyba"],
        )
        yesterday_row = YardSvozSubmitErrorLog.objects.get(message="včera chyba")
        self._backdate_error(yesterday_row, days_ago=1)
        today_pk = YardSvozSubmitErrorLog.objects.get(message="dnes chyba").pk

        self.client.force_login(self.disp)
        response = self.client.post(
            reverse(
                "waste_docs:svoz_submit_error_log_delete_selected",
                args=[self.subject.pk],
            ),
            {"next": "log", "subject": str(self.subject.pk), "error": [str(today_pk)]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(YardSvozSubmitErrorLog.objects.filter(pk=today_pk).exists())
        self.assertTrue(YardSvozSubmitErrorLog.objects.filter(message="včera chyba").exists())
        mock_reclaim.assert_called_once()

    @patch("waste_docs.services.svoz_matrix_submit_error_log.delete_selected.reclaim_sqlite_space_after_delete")
    def test_delete_selected_day_removes_errors_and_sent(self, mock_reclaim):
        from django.utils import timezone

        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["včera chyba"],
        )
        yesterday_error = YardSvozSubmitErrorLog.objects.get(message="včera chyba")
        self._backdate_error(yesterday_error, days_ago=1)
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["dnes chyba"],
        )
        pline = SvozPendingLine(
            pair=self.pair,
            matrix_display_label="Řádek",
            yard_contact_note="",
            container_numbers="OK-1",
        )
        sent_old = record_submission_log_line(
            pline=pline,
            subject=self.subject,
            user=self.yard_user,
            target_date=self.target,
        )
        self._backdate_sent(sent_old, days_ago=1)
        record_submission_log_line(
            pline=pline,
            subject=self.subject,
            user=self.yard_user,
            target_date=self.target,
            result_summary=RESULT_UNASSIGNED,
        )
        yesterday = timezone.localdate() - timedelta(days=1)

        self.client.force_login(self.disp)
        response = self.client.post(
            reverse(
                "waste_docs:svoz_submit_error_log_delete_selected",
                args=[self.subject.pk],
            ),
            {
                "next": "log",
                "subject": str(self.subject.pk),
                "day": [yesterday.isoformat()],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(YardSvozSubmitErrorLog.objects.filter(message="včera chyba").exists())
        self.assertTrue(YardSvozSubmitErrorLog.objects.filter(message="dnes chyba").exists())
        self.assertEqual(YardSvozSubmissionLog.objects.count(), 1)
        self.assertTrue(YardSvozSubmissionLog.objects.filter(result_summary=RESULT_UNASSIGNED).exists())
        mock_reclaim.assert_called_once()

    def test_yard_user_cannot_delete_selected(self):
        record_error_messages(
            subject=self.subject,
            user=self.yard_user,
            messages=["chyba C"],
        )
        pk = YardSvozSubmitErrorLog.objects.get().pk
        self.client.force_login(self.yard_user)
        response = self.client.post(
            reverse(
                "waste_docs:svoz_submit_error_log_delete_selected",
                args=[self.subject.pk],
            ),
            {"error": [str(pk)]},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(YardSvozSubmitErrorLog.objects.filter(pk=pk).exists())

    @patch("waste_docs.views.dispatch.svoz_request.svoz_subject_has_submitted_today", return_value=False)
    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_get_matrix_records_open_ready(self, mock_target, _submitted):
        from waste_docs.services.svoz_matrix_submit_error_log.record_open import MSG_MATRIX_READY
        from waste_docs.services.svoz_matrix_submit_error_log.query import dispatcher_alert_unread_count

        mock_target.return_value = self.target
        self.client.force_login(self.yard_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.OPEN)
        self.assertEqual(entry.message, MSG_MATRIX_READY)
        self.assertEqual(entry.created_by_id, self.yard_user.pk)
        self.assertEqual(list(rows_for_subject(subject_profile_id=self.subject.pk)), [])
        self.assertEqual(dispatcher_alert_unread_count(), 0)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_subject_has_submitted_today", return_value=True)
    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_get_matrix_records_open_closed(self, mock_target, _submitted):
        from waste_docs.services.svoz_matrix_submit_error_log.record_open import MSG_MATRIX_CLOSED

        mock_target.return_value = self.target
        self.client.force_login(self.yard_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.OPEN)
        self.assertEqual(entry.message, MSG_MATRIX_CLOSED)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_subject_has_submitted_today", return_value=False)
    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit")
    def test_get_matrix_open_throttled(self, mock_target, _submitted):
        mock_target.return_value = self.target
        self.client.force_login(self.yard_user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(YardSvozSubmitErrorLog.objects.filter(source="open").count(), 1)

    def test_record_yard_session_expired_writes_log_sd(self):
        from waste_docs.services.svoz_matrix_submit_error_log import record_yard_session_expired
        from waste_docs.services.svoz_matrix_submit_error_log.record_session import MSG_IDLE

        n = record_yard_session_expired(user=self.yard_user, reason="idle")
        self.assertEqual(n, 1)
        entry = YardSvozSubmitErrorLog.objects.get()
        self.assertEqual(entry.source, YardSvozSubmitErrorLog.Source.SESSION)
        self.assertEqual(entry.message, MSG_IDLE)
        self.assertEqual(entry.subject_profile_id, self.subject.pk)
        # Audit — ne v panelu chyb matice, ne v alertu
        self.assertEqual(list(rows_for_subject(subject_profile_id=self.subject.pk)), [])
        self.assertEqual(dispatcher_alert_unread_count(), 0)

    def test_login_page_shows_idle_notice(self):
        response = self.client.get(reverse("login"), {"reason": "idle", "next": "/"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nečinnosti")
