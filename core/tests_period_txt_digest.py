"""Testy Admin TXT výcucu období — izolovaný panel."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from customer_requests.models import CustomerRequest
from day_reminders.models import DayReminder
from users.constants import ROLE_ADMIN, ROLE_DISPECER
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka


@override_settings(ROOT_URLCONF="config.urls")
class PeriodTxtDigestTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("digest_admin", password="pw")
        set_user_role(self.admin, ROLE_ADMIN)
        self.disp = User.objects.create_user("digest_disp", password="pw")
        set_user_role(self.disp, ROLE_DISPECER)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.disp)
        prof.nav_reports = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_reports"])

        self.day = date(2037, 5, 12)
        name = NameCatalog.objects.create(value="Digest Subjekt")
        ico = IcoCatalog.objects.create(value="12345678")
        addr = AddressCatalog.objects.create(value="Ulice 1")
        wt = WasteTypeCatalog.objects.create(code="D01", value="Digest odpad")
        wc = WasteCodeCatalog.objects.create(value="20 01 01")
        wcat = WasteCategoryCatalog.objects.create(value="O")
        act = ActivityCatalog.objects.create(name="Digest činnost")

        self.ride = Pruvodka.objects.create(
            activity=act,
            name=name,
            ico=ico,
            address=addr,
            waste_type=wt,
            waste_code=wc,
            waste_category=wcat,
            drive_date=self.day,
            name_snapshot="Digest Subjekt",
            address_snapshot="Ulice 1",
            activity_snapshot="Digest činnost",
            waste_type_snapshot="Digest odpad",
            contact_note="pozn jizdy",
            created_by=self.admin,
        )
        self.cr = CustomerRequest.objects.create(
            created_by=self.admin,
            name=name,
            activity=act,
            waste_type=wt,
            address=addr,
            target_date=self.day,
            contact_note="do jizdy",
            note="k pozadavku",
            status=CustomerRequest.Status.DRAFT,
        )
        DayReminder.objects.create(
            title="Digest note",
            text="text poznámky",
            kind=DayReminder.Kind.ONE_OFF,
            pinned_date=self.day,
            created_by=self.admin,
        )

    def test_admin_sees_card_and_downloads_txt(self):
        c = Client()
        c.force_login(self.admin)
        hub = c.get(
            reverse("reports:index"),
            {"date_from": self.day.isoformat(), "date_to": self.day.isoformat()},
        )
        self.assertEqual(hub.status_code, 200)
        self.assertContains(hub, "Výcuc období (TXT)")

        page = c.get(
            reverse("reports:period_digest"),
            {"date_from": self.day.isoformat(), "date_to": self.day.isoformat()},
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Stáhnout TXT")

        resp = c.get(
            reverse("reports:period_digest_txt"),
            {"date_from": self.day.isoformat(), "date_to": self.day.isoformat()},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp["Content-Type"])
        body = resp.content.decode("utf-8")
        self.assertIn("########## JÍZDY ##########", body)
        self.assertIn("########## POŽADAVKY ##########", body)
        self.assertIn("########## POZNÁMKY ##########", body)
        self.assertIn(f"JÍZDA #{self.ride.pk}", body)
        self.assertIn(f"POŽADAVEK #{self.cr.pk}", body)
        self.assertIn("Digest note", body)
        self.assertIn("pozn jizdy", body)
        self.assertIn("k pozadavku", body)

    def test_dispatcher_gets_404(self):
        c = Client()
        c.force_login(self.disp)
        hub = c.get(reverse("reports:index"))
        self.assertEqual(hub.status_code, 200)
        self.assertNotContains(hub, "Výcuc období (TXT)")

        page = c.get(
            reverse("reports:period_digest"),
            {"date_from": self.day.isoformat(), "date_to": self.day.isoformat()},
        )
        self.assertEqual(page.status_code, 404)

        resp = c.get(
            reverse("reports:period_digest_txt"),
            {"date_from": self.day.isoformat(), "date_to": self.day.isoformat()},
        )
        self.assertEqual(resp.status_code, 404)
