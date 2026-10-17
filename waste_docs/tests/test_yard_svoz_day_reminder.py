"""Po odeslani hlaseni ze sberneho dvora — DayReminder pro dispecera."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

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
from day_reminders.models import DayReminder, DayReminderCompletion
from day_reminders.services.yard_dispatch_notes import yard_dispatch_notes_attention_for_date
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import SvozTask
from waste_docs.services.svoz_dispatch.yard_day_reminder import (
    build_yard_svoz_day_reminder_content,
    create_day_reminder_for_svoz_task,
    should_create_yard_dispatch_note,
)


class YardSvozDayReminderContentTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("yard_rem", password="pw")
        self.target = date(2033, 3, 15)
        self.name = NameCatalog.objects.create(value="Rem yard")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name, company_name="SD Rem Test",
        )
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="Odpad rem")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Hak", shortcut="H", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz rem")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_svoz_display_label="Matrace rem",
            yard_dispatch_note_enabled=True,
            yard_dispatch_note_title="Kontrola objemu",
            yard_dispatch_note_text="Pred svozem overit preplneni.",
        )
        self.task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.user,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="215, 218",
            matrix_display_label="Matrace rem",
            yard_contact_note="urgentni",
            target_date=self.target,
        )

    def test_build_content_uses_catalog_template_and_details(self):
        title, text = build_yard_svoz_day_reminder_content(self.task, self.pair)
        self.assertEqual(title, "Kontrola objemu")
        self.assertIn("Pred svozem overit preplneni.", text)
        self.assertIn("Kontejnery: 215, 218", text)
        self.assertIn("Poznámka ze dvora: urgentni", text)

    def test_build_content_fallback_title(self):
        self.pair.yard_dispatch_note_title = ""
        self.pair.save(update_fields=["yard_dispatch_note_title"])
        title, _ = build_yard_svoz_day_reminder_content(self.task, self.pair)
        self.assertEqual(title, "SD Rem Test · Matrace rem")

    def test_build_content_without_template_includes_subject(self):
        self.pair.yard_dispatch_note_text = ""
        self.pair.save(update_fields=["yard_dispatch_note_text"])
        _, text = build_yard_svoz_day_reminder_content(self.task, self.pair)
        self.assertIn("Subjekt: SD Rem Test", text)
        self.assertIn("Řádek matice: Matrace rem", text)

    def test_create_day_reminder(self):
        rem = create_day_reminder_for_svoz_task(
            task=self.task, pair=self.pair, created_by=self.user,
        )
        self.assertEqual(rem.kind, DayReminder.Kind.ONE_OFF)
        self.assertEqual(rem.pinned_date, self.target)
        self.assertEqual(rem.title, "Kontrola objemu")
        self.assertEqual(rem.source_svoz_task_id, self.task.pk)

    def test_should_create_when_enabled(self):
        self.assertTrue(should_create_yard_dispatch_note(self.pair))
        self.pair.yard_dispatch_note_enabled = False
        self.assertFalse(should_create_yard_dispatch_note(self.pair))


class YardDispatchNotesAttentionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("attn", password="pw")
        self.target = date(2033, 5, 1)
        self.name = NameCatalog.objects.create(value="Attn yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Attn")
        self.wt = WasteTypeCatalog.objects.create(code="200303", value="Odpad attn")
        self.suf = SuffixCatalog.objects.create(value="KV3")
        self.vk = VehicleKindCatalog.objects.create(name="Hak3", shortcut="H3", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz attn")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_dispatch_note_enabled=True,
            yard_dispatch_note_title="Attn note",
        )
        self.task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.user,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            target_date=self.target,
        )

    def test_attention_for_unresolved_note(self):
        create_day_reminder_for_svoz_task(
            task=self.task, pair=self.pair, created_by=self.user,
        )
        attention, count = yard_dispatch_notes_attention_for_date(self.target)
        self.assertTrue(attention)
        self.assertEqual(count, 1)

    def test_no_attention_when_resolved(self):
        rem = create_day_reminder_for_svoz_task(
            task=self.task, pair=self.pair, created_by=self.user,
        )
        DayReminderCompletion.objects.create(
            reminder=rem, resolved_on=self.target, resolved_by=self.user,
        )
        attention, count = yard_dispatch_notes_attention_for_date(self.target)
        self.assertFalse(attention)
        self.assertEqual(count, 0)

    def test_no_attention_for_svoz_task_without_note(self):
        attention, count = yard_dispatch_notes_attention_for_date(self.target)
        self.assertFalse(attention)
        self.assertEqual(count, 0)


class YardSvozDayReminderFlowTests(TestCase):
    def setUp(self):
        self.target = date(2033, 4, 10)
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_flow", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        self.admin = User.objects.create_user("disp_flow", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Flow yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Flow")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt = WasteTypeCatalog.objects.create(code="200302", value="Odpad flow", category="O")
        self.suf = SuffixCatalog.objects.create(value="KV2")
        self.vk = VehicleKindCatalog.objects.create(name="Hak2", shortcut="H2", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz flow")
        ContainerPassport.objects.create(container_number="FL-1", vehicle_kind=self.vk, color="—")

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            yard_dispatch_note_enabled=True,
            yard_dispatch_note_title="Flow poznamka",
            yard_dispatch_note_text="Sablona flow",
        )

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit", return_value=date(2033, 4, 10))
    def test_post_without_dispatch_note_flag_creates_task_only(self, _mock_target):
        self.pair.yard_dispatch_note_enabled = False
        self.pair.save(update_fields=["yard_dispatch_note_enabled"])
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "FL-1",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)
        self.assertEqual(DayReminder.objects.filter(source_svoz_task__isnull=False).count(), 0)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit", return_value=date(2033, 4, 10))
    def test_post_multiple_containers_one_day_reminder(self, _mock_target):
        ContainerPassport.objects.create(container_number="FL-2", vehicle_kind=self.vk, color="—")
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "FL-1\nFL-2",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 2)
        self.assertEqual(DayReminder.objects.filter(title="Flow poznamka").count(), 1)

    @patch("waste_docs.views.dispatch.svoz_request.svoz_target_date_for_matrix_submit", return_value=date(2033, 4, 10))
    def test_post_creates_day_reminder_not_for_hazard(self, _mock_target):
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair.pk)],
                f"containers_{self.pair.pk}": "FL-1",
                f"note_{self.pair.pk}": "dnes rychle",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)
        self.assertEqual(DayReminder.objects.filter(title="Flow poznamka").count(), 1)
        rem = DayReminder.objects.get(title="Flow poznamka")
        self.assertEqual(rem.pinned_date, self.target)
        self.assertIn("Sablona flow", rem.text)
        self.assertIn("dnes rychle", rem.text)
        task = SvozTask.objects.get(subject_profile=self.subject)
        self.assertEqual(rem.source_svoz_task_id, task.pk)

    def test_dashboard_shows_attention_banner_for_unresolved_note(self):
        task = SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.yard_user,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="FL-1",
            target_date=self.target,
        )
        create_day_reminder_for_svoz_task(
            task=task, pair=self.pair, created_by=self.yard_user,
        )
        client = Client()
        client.force_login(self.admin)
        dash_url = reverse("core:dashboard") + f"?date={self.target.isoformat()}"
        r = client.get(dash_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dash-yard-svoz-attention-banner")
        self.assertContains(r, "Nová poznámka ze sběrného dvora")
        self.assertContains(r, "nevyřešená poznámka")

    def test_dashboard_no_banner_for_svoz_task_only(self):
        SvozTask.objects.create(
            subject_profile=self.subject,
            created_by=self.yard_user,
            waste_type=self.wt,
            suffix=self.suf,
            source_waste_suffix_pair=self.pair,
            vehicle_kind=self.vk,
            activity=self.activity,
            container_numbers="FL-1",
            target_date=self.target,
        )
        client = Client()
        client.force_login(self.admin)
        dash_url = reverse("core:dashboard") + f"?date={self.target.isoformat()}"
        r = client.get(dash_url)
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Nová poznámka ze sběrného dvora")
