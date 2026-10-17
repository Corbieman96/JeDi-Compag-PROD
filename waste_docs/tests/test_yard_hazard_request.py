"""Nebezpečný odpad ze sběrného dvora — plovoucí požadavek bez auto-jízdy."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import Client, TestCase
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
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from users.constants import ROLE_ADMIN, ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka, SvozTask, SvozYardDriverPlan, YardHazardousWasteRequest
from waste_docs.services.yard_hazard_request import (
    create_hazard_request_from_line,
    is_hazardous_waste_type,
    open_hazard_requests_for_dashboard,
    resolve_hazard_request_with_pruvodka,
    submit_hazard_line_if_allowed,
)
from waste_docs.services.svoz_matrix_post_collect import collect_pending_svoz_matrix_lines
from waste_docs.services.svoz_matrix_post_collect import SvozPendingLine


class YardHazardDetectionTests(TestCase):
    def test_category_nebezpecny_is_hazardous(self):
        wt = WasteTypeCatalog.objects.create(code="200101", value="NO test", category="Nebezpečný")
        self.assertTrue(is_hazardous_waste_type(wt))

    def test_category_obycejny_is_not_hazardous(self):
        wt = WasteTypeCatalog.objects.create(code="200201", value="O test", category="O")
        self.assertFalse(is_hazardous_waste_type(wt))


class YardHazardRequestFlowTests(TestCase):
    def setUp(self):
        self.target = date(2032, 6, 18)
        self.later = self.target + timedelta(days=3)
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_hazard", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        self.admin = User.objects.create_user("disp_hazard", password="pw", is_superuser=True)
        set_user_role(self.admin, ROLE_ADMIN)

        self.name = NameCatalog.objects.create(value="Hazard yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Hazard")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        self.wt_hazard = WasteTypeCatalog.objects.create(code="150110", value="NO odpad", category="N")
        self.wt_normal = WasteTypeCatalog.objects.create(code="200301", value="Odpad O", category="O")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz hazard")
        ContainerPassport.objects.create(container_number="HZ-1", vehicle_kind=self.vk, color="—")
        ContainerPassport.objects.create(container_number="OK-1", vehicle_kind=self.vk, color="—")

        self.pair_hazard = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_hazard,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pair_normal = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_normal,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )

        from catalogs.models import DriverProfile

        self.driver = DriverProfile.objects.create(personal_number="HZ1", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="1H11111")
        prof_rz = VehicleRzProfile.objects.create(rz=self.rz)
        prof_rz.vehicle_kinds.add(self.vk)
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

    def test_hazard_post_creates_request_not_svoz_task(self):
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair_hazard.pk)],
                f"containers_{self.pair_hazard.pk}": "HZ-1",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(YardHazardousWasteRequest.objects.filter(subject_profile=self.subject).count(), 1)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 0)
        self.assertEqual(Pruvodka.objects.filter(name=self.name).count(), 0)

    def test_mixed_post_splits_hazard_and_standard(self):
        client = Client()
        client.force_login(self.yard_user)
        url = reverse("waste_docs:svoz_request")
        r = client.post(
            url,
            {
                "pair_pk": [str(self.pair_hazard.pk), str(self.pair_normal.pk)],
                f"containers_{self.pair_hazard.pk}": "HZ-1",
                f"containers_{self.pair_normal.pk}": "OK-1",
            },
            follow=True,
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(YardHazardousWasteRequest.objects.filter(subject_profile=self.subject).count(), 1)
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)

    def test_open_request_floats_on_later_dashboard_days(self):
        pline = SvozPendingLine(
            pair=self.pair_hazard,
            matrix_display_label="Matrace NO",
            yard_contact_note="",
            container_numbers="HZ-1",
        )
        req = create_hazard_request_from_line(pline, self.subject, self.yard_user)
        req.submitted_date = self.target
        req.save(update_fields=["submitted_date"])

        on_target = open_hazard_requests_for_dashboard(self.admin, self.target)
        on_later = open_hazard_requests_for_dashboard(self.admin, self.later)
        self.assertEqual(len(on_target), 1)
        self.assertEqual(len(on_later), 1)

        ride = Pruvodka.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="11111111"),
            address=AddressCatalog.objects.create(value="Adr hazard"),
            waste_type=self.wt_hazard,
            waste_code=WasteCodeCatalog.objects.create(value="WCH"),
            waste_category=WasteCategoryCatalog.objects.create(value="N"),
            suffix=self.suf,
            drive_date=self.later,
            created_by=self.admin,
        )
        resolve_hazard_request_with_pruvodka(req, ride)
        self.assertEqual(open_hazard_requests_for_dashboard(self.admin, self.later), [])

    def test_dashboard_contains_hazard_section(self):
        pline = SvozPendingLine(
            pair=self.pair_hazard,
            matrix_display_label="NO řádek",
            yard_contact_note="",
            container_numbers="HZ-1",
        )
        create_hazard_request_from_line(pline, self.subject, self.yard_user)
        client = Client()
        client.force_login(self.admin)
        dash_url = reverse("core:dashboard") + f"?date={timezone.localdate().isoformat()}"
        r = client.get(dash_url)
        self.assertContains(r, "Nebezpečný odpad ze dvora")
        self.assertContains(r, "yard_hazard_request=")


class YardHazardSubmitDedupTests(TestCase):
    def setUp(self):
        from core.models import AppSettings

        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_hazard_dedup", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        self.admin = User.objects.create_user("disp_hazard_dedup", password="pw", is_superuser=True)

        self.name = NameCatalog.objects.create(value="Hazard dedup yard")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="SD Dedup")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_matrix = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        settings_obj = AppSettings.load()
        settings_obj.svoz_disable_yard_daily_submit_limit = True
        settings_obj.save(update_fields=["svoz_disable_yard_daily_submit_limit"])

        self.wt_hazard_a = WasteTypeCatalog.objects.create(code="150111", value="NO A", category="N")
        self.wt_hazard_b = WasteTypeCatalog.objects.create(code="150112", value="NO B", category="N")
        self.wt_normal = WasteTypeCatalog.objects.create(code="200302", value="Odpad O dedup", category="O")
        self.suf = SuffixCatalog.objects.create(value="KV dedup")
        self.vk = VehicleKindCatalog.objects.create(name="Hák dedup", shortcut="HD", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz dedup")
        ContainerPassport.objects.create(container_number="DD-1", vehicle_kind=self.vk, color="—")
        ContainerPassport.objects.create(container_number="DD-2", vehicle_kind=self.vk, color="—")
        ContainerPassport.objects.create(container_number="DD-3", vehicle_kind=self.vk, color="—")

        self.pair_hazard_a = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_hazard_a,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pair_hazard_b = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_hazard_b,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )
        self.pair_normal = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt_normal,
            suffix=self.suf,
            yard_svoz_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
        )

        from catalogs.models import DriverProfile, VehicleRzCatalog
        from catalogs.models.vehicle_rz import VehicleRzProfile
        from waste_docs.models import SvozYardDriverPlan
        from waste_docs.svoz_schedule import next_svoz_target_date

        self.target = next_svoz_target_date()
        self.driver = DriverProfile.objects.create(personal_number="DD1", last_name="Řidič dedup")
        self.rz = VehicleRzCatalog.objects.create(value="1D11111")
        prof_rz = VehicleRzProfile.objects.create(rz=self.rz)
        prof_rz.vehicle_kinds.add(self.vk)
        SvozYardDriverPlan.objects.create(
            plan_date=self.target,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

    def _post_matrix(self, data):
        client = Client()
        client.force_login(self.yard_user)
        return client.post(reverse("waste_docs:svoz_request"), data, follow=False)

    def test_duplicate_hazard_submit_does_not_create_second_request(self):
        payload = {
            "pair_pk": [str(self.pair_hazard_a.pk)],
            f"containers_{self.pair_hazard_a.pk}": "DD-1",
        }
        self.assertEqual(self._post_matrix(payload).status_code, 302)
        req = YardHazardousWasteRequest.objects.get(subject_profile=self.subject, source_waste_suffix_pair=self.pair_hazard_a)
        self.assertEqual(req.container_numbers, "DD-1")

        payload_dup = {
            "pair_pk": [str(self.pair_hazard_a.pk)],
            f"containers_{self.pair_hazard_a.pk}": "DD-2",
        }
        self.assertEqual(self._post_matrix(payload_dup).status_code, 302)
        self.assertEqual(
            YardHazardousWasteRequest.objects.filter(
                subject_profile=self.subject,
                source_waste_suffix_pair=self.pair_hazard_a,
            ).count(),
            1,
        )
        req.refresh_from_db()
        self.assertEqual(req.container_numbers, "DD-1")

    def test_duplicate_hazard_allows_other_pair(self):
        self._post_matrix(
            {
                "pair_pk": [str(self.pair_hazard_a.pk)],
                f"containers_{self.pair_hazard_a.pk}": "DD-1",
            }
        )
        self._post_matrix(
            {
                "pair_pk": [str(self.pair_hazard_b.pk)],
                f"containers_{self.pair_hazard_b.pk}": "DD-2",
            }
        )
        self.assertEqual(YardHazardousWasteRequest.objects.filter(subject_profile=self.subject).count(), 2)

    def test_duplicate_hazard_mixed_with_normal_svoz(self):
        create_hazard_request_from_line(
            SvozPendingLine(
                pair=self.pair_hazard_a,
                matrix_display_label="NO dedup mix",
                yard_contact_note="",
                container_numbers="DD-1",
            ),
            self.subject,
            self.yard_user,
        )
        response = self._post_matrix(
            {
                "pair_pk": [str(self.pair_hazard_a.pk), str(self.pair_normal.pk)],
                f"containers_{self.pair_hazard_a.pk}": "DD-2",
                f"containers_{self.pair_normal.pk}": "DD-3",
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            YardHazardousWasteRequest.objects.filter(
                subject_profile=self.subject,
                source_waste_suffix_pair=self.pair_hazard_a,
            ).count(),
            1,
        )
        self.assertEqual(SvozTask.objects.filter(subject_profile=self.subject).count(), 1)

    def test_after_resolve_can_submit_again(self):
        pline = SvozPendingLine(
            pair=self.pair_hazard_a,
            matrix_display_label="NO dedup",
            yard_contact_note="",
            container_numbers="DD-1",
        )
        req = create_hazard_request_from_line(pline, self.subject, self.yard_user)
        ride = Pruvodka.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="22222222"),
            address=AddressCatalog.objects.create(value="Adr dedup"),
            waste_type=self.wt_hazard_a,
            waste_code=WasteCodeCatalog.objects.create(value="WCD"),
            waste_category=WasteCategoryCatalog.objects.create(value="N"),
            suffix=self.suf,
            drive_date=timezone.localdate(),
            created_by=self.admin,
        )
        resolve_hazard_request_with_pruvodka(req, ride)

        result = submit_hazard_line_if_allowed(
            SvozPendingLine(
                pair=self.pair_hazard_a,
                matrix_display_label="NO dedup 2",
                yard_contact_note="",
                container_numbers="DD-2",
            ),
            self.subject,
            self.yard_user,
        )
        self.assertTrue(result.created)
        self.assertEqual(
            YardHazardousWasteRequest.objects.filter(
                subject_profile=self.subject,
                source_waste_suffix_pair=self.pair_hazard_a,
                status=YardHazardousWasteRequest.Status.OPEN,
            ).count(),
            1,
        )

    def test_only_duplicate_redirects_without_error(self):
        self._post_matrix(
            {
                "pair_pk": [str(self.pair_hazard_a.pk)],
                f"containers_{self.pair_hazard_a.pk}": "DD-1",
            }
        )
        response = self._post_matrix(
            {
                "pair_pk": [str(self.pair_hazard_a.pk)],
                f"containers_{self.pair_hazard_a.pk}": "DD-2",
            }
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("waste_docs:yard_hub"))
