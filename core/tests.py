from pathlib import Path
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from catalogs.models import DriverProfile, NameCatalog, NameSubjectProfile, VehicleRzCatalog
from catalogs.models.vehicle_rz import VehicleKindCatalog
from config.env.default_database import get_default_database_config
from users.models import UserAccessProfile


class SettingsTests(SimpleTestCase):
    def test_time_zone_prague_for_local_dates(self):
        self.assertEqual(settings.TIME_ZONE, "Europe/Prague")


class DefaultDatabaseConfigTests(SimpleTestCase):
    def test_sqlite_when_database_url_empty(self):
        base = Path(__file__).resolve().parent.parent
        with patch.dict("os.environ", {"DATABASE_URL": ""}, clear=False):
            cfg = get_default_database_config(base)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["NAME"], base / "db.sqlite3")

    def test_sqlite_relative_database_url_uses_base_dir(self):
        base = Path(__file__).resolve().parent.parent
        url = "sqlite:///db.sqlite3"
        with patch.dict("os.environ", {"DATABASE_URL": url}, clear=False):
            cfg = get_default_database_config(base)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(cfg["NAME"], (base / "db.sqlite3").resolve())

    def test_postgresql_when_database_url_set(self):
        base = Path(__file__).resolve().parent.parent
        url = "postgresql://app:secret@db.local:5432/jedis_test"
        with patch.dict("os.environ", {"DATABASE_URL": url}, clear=False):
            cfg = get_default_database_config(base)
        self.assertEqual(cfg["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(cfg["NAME"], "jedis_test")
        self.assertEqual(cfg["USER"], "app")
        self.assertEqual(cfg["PASSWORD"], "secret")
        self.assertEqual(cfg["HOST"], "db.local")
        self.assertEqual(cfg["PORT"], 5432)


class DashboardDriverPortalBadgeTests(TestCase):
    """Indikátor propojení portálu v panelu Řidiči na dashboardu."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_portal_admin", password="pw", is_superuser=True)
        self.d_linked = DriverProfile.objects.create(personal_number="DASH-P-L", last_name="Propojeny")
        self.d_plain = DriverProfile.objects.create(personal_number="DASH-P-N", last_name="Nepropojeny")
        self.portal_user = User.objects.create_user("dash_portal_u", password="pw")
        UserAccessProfile.objects.update_or_create(
            user=self.portal_user,
            defaults={"driver_profile_id": self.d_linked.pk},
        )

    def test_dashboard_driver_panel_shows_portal_on_and_off(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dash-driver-portal-icon--on")
        self.assertNotContains(r, "dash-driver-portal-icon--off")
        self.assertContains(r, 'aria-label="Portál řidiče, účet propojen"')
        self.assertNotContains(r, "účet není propojen")


class DashboardPartialDoctorBadgeTests(TestCase):
    """Půldenní lékař musí být vidět v panelu Řidiči; celodenní lékaře panel schová."""

    def setUp(self):
        from catalogs.models import DriverAbsence

        User = get_user_model()
        self.admin = User.objects.create_user("dash_doc_admin", password="pw", is_superuser=True)
        self.day = date(2027, 8, 18)
        self.partial = DriverProfile.objects.create(
            personal_number="DOC-HALF", last_name="Puldenni", first_name="Lekar"
        )
        self.full = DriverProfile.objects.create(
            personal_number="DOC-FULL", last_name="Celodenni", first_name="Lekar"
        )
        DriverAbsence.objects.create(
            driver=self.partial,
            absence_type=DriverAbsence.AbsenceType.DOCTOR,
            date_from=self.day,
            date_to=self.day,
            is_partial=True,
        )
        DriverAbsence.objects.create(
            driver=self.full,
            absence_type=DriverAbsence.AbsenceType.DOCTOR,
            date_from=self.day,
            date_to=self.day,
            is_partial=False,
        )

    def test_partial_doctor_shows_in_drivers_panel_full_day_hidden(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("core:dashboard"), {"date": self.day.isoformat()})
        self.assertEqual(r.status_code, 200)
        visible_last_names = [d.last_name for d in r.context["drivers"]]
        self.assertIn("Puldenni", visible_last_names)
        self.assertNotIn("Celodenni", visible_last_names)
        self.assertContains(r, "dash-driver-partial-absence-icon")
        self.assertContains(r, "½ Lékař / vyšetření")


class DashboardOtherAbsenceStaysInDriversPanelTests(TestCase):
    """Jiné zůstane v panelu Řidiči; dovolená dál spadne do nepřítomností."""

    def setUp(self):
        from catalogs.models import DriverAbsence

        User = get_user_model()
        self.admin = User.objects.create_user("dash_other_admin", password="pw", is_superuser=True)
        self.day = date(2027, 9, 4)
        self.other_driver = DriverProfile.objects.create(
            personal_number="OTH-1", last_name="Jiny", first_name="Ridic"
        )
        self.vacation_driver = DriverProfile.objects.create(
            personal_number="VAC-1", last_name="Dovolena", first_name="Ridic"
        )
        self.other_absence = DriverAbsence.objects.create(
            driver=self.other_driver,
            absence_type=DriverAbsence.AbsenceType.OTHER,
            date_from=self.day,
            date_to=self.day,
            is_partial=False,
            note="Školení mimo katalog",
        )
        DriverAbsence.objects.create(
            driver=self.vacation_driver,
            absence_type=DriverAbsence.AbsenceType.VACATION,
            date_from=self.day,
            date_to=self.day,
            is_partial=False,
        )

    def test_other_stays_in_drivers_vacation_in_absence_strip(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("core:dashboard"), {"date": self.day.isoformat()})
        self.assertEqual(r.status_code, 200)
        visible = [d.last_name for d in r.context["drivers"]]
        self.assertIn("Jiny", visible)
        self.assertNotIn("Dovolena", visible)
        absence_names = [
            (row.get("driver").last_name if row.get("driver") else "")
            for row in r.context["absence_panel_rows"]
        ]
        self.assertNotIn("Jiny", absence_names)
        self.assertIn("Dovolena", absence_names)
        other = next(d for d in r.context["drivers"] if d.last_name == "Jiny")
        self.assertIn("Jiné", other.partial_absence_label)
        self.assertIn("Školení mimo katalog", other.partial_absence_label)
        self.assertIsNotNone(other.panel_other_absence)
        self.assertEqual(other.panel_other_absence.pk, self.other_absence.pk)
        update_url = reverse(
            "catalogs:driver_absence_quick_update",
            args=[self.other_driver.pk, self.other_absence.pk],
        )
        delete_url = reverse(
            "catalogs:driver_absence_quick_delete",
            args=[self.other_driver.pk, self.other_absence.pk],
        )
        self.assertContains(r, update_url)
        self.assertContains(r, delete_url)
        self.assertContains(r, "Zrušit Jiné")


class DashboardDispatchFailSafeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_fail_safe_admin", password="pw", is_superuser=True)

    def test_dashboard_render_survives_dispatch_exception(self):
        c = Client()
        c.force_login(self.admin)
        with patch(
            "core.services.dashboard_context.build_dashboard_dispatch_context",
            side_effect=RuntimeError("dispatch boom"),
        ):
            r = c.get(reverse("core:dashboard"), {"date": "2026-09-13"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Dashboard běží v nouzovém režimu")


class DashboardSvozPlanBridgeTests(TestCase):
    """Plán svozů bez průvodky — dashboard indikátory řidiče a skupiny jízd."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_svoz_plan_adm", password="pw", is_superuser=True)
        self.plan_date = date(2027, 3, 15)
        self.dr = DriverProfile.objects.create(personal_number="PB-998", last_name="Plannerský", first_name="Pavel")
        self.rz = VehicleRzCatalog.objects.create(value="1T9999999")
        self.vk = VehicleKindCatalog.objects.create(name="Druh pro test plánu", shortcut="PV", sort_order=0)
        nm = NameCatalog.objects.create(value="Subjekt pro test plánu dashboardu XYZ")
        self.subject = NameSubjectProfile.objects.create(name=nm, company_name="Yard Dashboard Test Ltd")
        ys = self.subject.yard_settings
        ys.is_collection_yard = True
        ys.save(update_fields=["is_collection_yard"])
        from waste_docs.models import SvozYardDriverPlan

        SvozYardDriverPlan.objects.create(
            plan_date=self.plan_date,
            subject_profile=self.subject,
            driver=self.dr,
            vehicle_rz=self.rz,
            row_kind="standard",
            vehicle_kind=self.vk,
            sort_order=0,
        )

    def test_driver_ids_with_planned_svoz_slots(self):
        from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import driver_ids_with_planned_svoz_slots

        self.assertEqual(driver_ids_with_planned_svoz_slots(self.plan_date), frozenset({self.dr.pk}))

    def test_planned_svoz_vehicle_groups_skip_occupied_rz_driver_pair(self):
        from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import planned_svoz_vehicle_groups

        occupied = frozenset({(self.rz.pk, self.dr.pk)})
        self.assertEqual(len(planned_svoz_vehicle_groups(self.plan_date, occupied)), 0)
        gps = planned_svoz_vehicle_groups(self.plan_date, frozenset())
        self.assertEqual(len(gps), 1)
        self.assertTrue(gps[0]["is_plan_only"])
        self.assertEqual(gps[0]["vehicle_rz_id"], self.rz.pk)
        self.assertEqual(gps[0]["driver_id"], self.dr.pk)
        self.assertEqual(gps[0]["status"], "Plán svozů")

    def test_plan_stub_hidden_when_org_has_pruvodka_even_for_other_user(self):
        from catalogs.models import (
            AddressCatalog,
            IcoCatalog,
            SuffixCatalog,
            WasteCategoryCatalog,
            WasteCodeCatalog,
            WasteTypeCatalog,
        )

        from core.services.dashboard_rides import org_occupied_rz_driver_pairs
        from waste_docs.models import Pruvodka
        from waste_docs.services.svoz_dispatch.dashboard_plan_bridge import planned_svoz_vehicle_groups

        other = get_user_model().objects.create_user("dash_org_occ_other", password="pw")
        name_for_p = NameCatalog.objects.create(value="Nm orgstub dash")
        Pruvodka.objects.create(
            name=name_for_p,
            ico=IcoCatalog.objects.create(value="55443322"),
            address=AddressCatalog.objects.create(value="Adr dash orgstub"),
            waste_type=WasteTypeCatalog.objects.create(code="990011", value="Worgstub"),
            waste_code=WasteCodeCatalog.objects.create(value="WCORG"),
            waste_category=WasteCategoryCatalog.objects.create(value="KO"),
            suffix=SuffixCatalog.objects.create(value="SFXORG"),
            drive_date=self.plan_date,
            vehicle_rz=self.rz,
            driver=self.dr,
            container_number="",
            created_by=other,
        )
        occupied = org_occupied_rz_driver_pairs(self.plan_date)
        self.assertIn((self.rz.pk, self.dr.pk), occupied)
        self.assertEqual(planned_svoz_vehicle_groups(self.plan_date, occupied), [])

    def test_dashboard_driver_plan_badge_without_exclamation_when_only_svoz_plan(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("core:dashboard"), {"date": self.plan_date.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dash-driver-planned-svoz-icon")
        self.assertNotContains(r, "dash-driver-no-ride-icon")
        self.assertContains(r, "Plán svozů")
        self.assertContains(r, "1T9999999")


class DashboardRideListVehicleKindTests(TestCase):
    """Sloupec Druh v panelu Seznam jízd na dashboardu."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_kind_admin", password="pw", is_superuser=True)
        self.ride_date = date(2027, 4, 10)
        self.rz = VehicleRzCatalog.objects.create(value="1A11111")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_r = VehicleKindCatalog.objects.create(name="Řetěz", shortcut="Ř", sort_order=2)
        from catalogs.models.vehicle_rz import VehicleRzProfile

        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk_h, self.vk_r)
        from catalogs.models import (
            AddressCatalog,
            IcoCatalog,
            SuffixCatalog,
            WasteCategoryCatalog,
            WasteCodeCatalog,
            WasteTypeCatalog,
        )
        from waste_docs.models import Pruvodka

        name = NameCatalog.objects.create(value="Subjekt druh dashboard")
        Pruvodka.objects.create(
            name=name,
            ico=IcoCatalog.objects.create(value="11223344"),
            address=AddressCatalog.objects.create(value="Adr druh dash"),
            waste_type=WasteTypeCatalog.objects.create(code="990012", value="Wdruh"),
            waste_code=WasteCodeCatalog.objects.create(value="WCDR"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOD"),
            suffix=SuffixCatalog.objects.create(value="SFXDR"),
            drive_date=self.ride_date,
            vehicle_rz=self.rz,
            container_number="",
            created_by=self.admin,
        )

    def test_build_dashboard_rides_section_vehicle_kind_tags(self):
        from core.services.dashboard_rides import build_dashboard_rides_section

        ctx, _ = build_dashboard_rides_section(self.admin, self.ride_date, "")
        group = next(g for g in ctx["ride_groups"] if g["vehicle_rz_id"] == self.rz.pk)
        self.assertEqual(group["vehicle_kind_shortcuts_label"], "H · Ř")
        self.assertEqual(
            [t["shortcut"] for t in group["vehicle_kind_tags"]],
            ["H", "Ř"],
        )
        self.assertEqual(group["vehicle_kind_tags"][0]["title"], "Hák (H)")

    def test_dashboard_rides_panel_shows_vehicle_kind_shortcuts(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("core:dashboard"), {"date": self.ride_date.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "dash-vehicle-kind-shortcut")
        self.assertContains(r, 'title="Hák (H)"')
        self.assertContains(r, 'title="Řetěz (Ř)"')
        self.assertContains(r, ">H<")
        self.assertContains(r, ">Ř<")
        self.assertContains(r, 'scope="col">Druh</th>')
        self.assertContains(r, 'class="dash-rides-col-count" title="Počet průvodek"')
        self.assertNotContains(r, "Počet průvodek</th>")


class DashboardWeekdayLabelTests(TestCase):
    """Den v týdnu nad date pickerem v mastheadu dashboardu."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("dash_weekday_admin", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.admin)

    def test_dashboard_shows_weekday_above_date_picker(self):
        response = self.client.get(reverse("core:dashboard"), {"date": "2037-03-10"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="dash-date-toolbar__weekday"')
        self.assertContains(response, "úterý")
