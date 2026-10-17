"""Testy portálu řidiče a QR párování."""

from datetime import date
import uuid

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from driver_portal.models import DriverPortalPairingToken
from users.constants import ROLE_RIDIC, ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka

User = get_user_model()


def _minimal_pruvodka(*, created_by, driver: DriverProfile | None, drive_date: date | None = None):
    suffix = uuid.uuid4().hex[:8]
    name = NameCatalog.objects.create(value=f"Subjekt T {suffix}")
    ico = IcoCatalog.objects.create(value=f"{suffix[:8]}".ljust(8, "0")[:8])
    addr = AddressCatalog.objects.create(value=f"Testovací ulice {suffix}")
    wt = WasteTypeCatalog.objects.create(code=f"WT{suffix[:6]}", value=f"Typ T {suffix}")
    wc = WasteCodeCatalog.objects.create(value=f"C{suffix[:4]}")
    wcat = WasteCategoryCatalog.objects.create(value=f"K{suffix[:4]}")
    kwargs = dict(
        name=name,
        ico=ico,
        address=addr,
        waste_type=wt,
        waste_code=wc,
        waste_category=wcat,
        created_by=created_by,
        driver=driver,
    )
    if drive_date is not None:
        kwargs["drive_date"] = drive_date
    return Pruvodka.objects.create(**kwargs)


class DriverPortalPairingTests(TestCase):
    def setUp(self):
        self.driver_a = DriverProfile.objects.create(personal_number="DP-100", last_name="Řidič", first_name="A")
        self.driver_b = DriverProfile.objects.create(personal_number="DP-200", last_name="Řidič", first_name="B")
        self.staff = User.objects.create_user(username="dp_staff", password="pw", is_superuser=True)
        self.ridic_u = User.objects.create_user(username="dp_ridic", password="pw")
        set_user_role(self.ridic_u, ROLE_RIDIC)
        self.zadavatel_u = User.objects.create_user(username="dp_zad", password="pw")
        set_user_role(self.zadavatel_u, ROLE_ZADAVATEL)

    def test_pairing_requires_ridic_role(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        c.force_login(self.zadavatel_u)
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.get(url)
        self.assertEqual(r.status_code, 403)

    def test_pairing_active_links_profile(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(url)
        self.assertEqual(r.status_code, 302)
        prof = UserAccessProfile.objects.get(user=self.ridic_u)
        self.assertEqual(prof.driver_profile_id, self.driver_a.pk)

    def test_pairing_rejects_when_driver_linked_elsewhere(self):
        other = User.objects.create_user(username="dp_other", password="pw")
        set_user_role(other, ROLE_RIDIC)
        UserAccessProfile.objects.update_or_create(
            user=other,
            defaults={"driver_profile_id": self.driver_a.pk},
        )
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(url)
        self.assertEqual(r.status_code, 409)

    def test_pairing_paused_returns_403(self):
        token = DriverPortalPairingToken.objects.create(
            driver=self.driver_a,
            status=DriverPortalPairingToken.Status.PAUSED,
        )
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.get(url)
        self.assertEqual(r.status_code, 403)

    def test_authenticated_other_driver_shows_compare_and_logout_retry(self):
        UserAccessProfile.objects.update_or_create(
            user=self.ridic_u,
            defaults={"driver_profile_id": self.driver_a.pk},
        )
        token_b = DriverPortalPairingToken.objects.create(driver=self.driver_b)
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:pair", kwargs={"secret": token_b.secret})
        r = c.get(url)
        self.assertEqual(r.status_code, 409)
        self.assertContains(r, "DP-200", status_code=409)
        self.assertContains(r, "DP-100", status_code=409)
        self.assertContains(r, "Odhlásit se", status_code=409)
        retry = reverse("driver_portal:pair_logout_retry", kwargs={"secret": token_b.secret})
        r2 = c.post(retry)
        self.assertEqual(r2.status_code, 302)
        r3 = c.get(url)
        self.assertEqual(r3.status_code, 200)
        self.assertContains(r3, token_b.display_code)

    def test_anonymous_get_shows_login_with_display_code(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        self.assertGreater(len(token.display_code), 0)
        c = Client()
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, token.display_code)

    def test_anonymous_post_passwordless_pairs_auto_portal_user(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(url, {"display_code": token.display_code})
        self.assertEqual(r.status_code, 302)
        from driver_portal.services.portal_driver_user import username_portal_driver_auto

        uname = username_portal_driver_auto(self.driver_a.pk)
        user = User.objects.get(username=uname)
        prof = UserAccessProfile.objects.get(user=user)
        self.assertEqual(prof.driver_profile_id, self.driver_a.pk)
        self.assertTrue(c.session.session_key)

    def test_anonymous_passwordless_uses_existing_linked_user(self):
        UserAccessProfile.objects.update_or_create(
            user=self.ridic_u,
            defaults={"driver_profile_id": self.driver_a.pk},
        )
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(url, {"display_code": token.display_code})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(c.session["_auth_user_id"]), self.ridic_u.pk)
        self.assertFalse(User.objects.filter(username="portal_driver_%s" % self.driver_a.pk).exists())

    def test_anonymous_post_rejects_wrong_display_code(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(
            url,
            {
                "display_code": "ZZZZ-ZZZZ",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Kód pozvánky")
        self.assertFalse(
            UserAccessProfile.objects.filter(
                user=self.ridic_u,
                driver_profile_id=self.driver_a.pk,
            ).exists()
        )

    def test_pairing_cookie_returns_without_password(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver_a)
        c = Client()
        url = reverse("driver_portal:pair", kwargs={"secret": token.secret})
        r = c.post(
            url,
            {"display_code": token.display_code},
        )
        self.assertEqual(r.status_code, 302)
        plink = r.cookies.get("dp_plink")
        self.assertIsNotNone(plink)
        c2 = Client()
        c2.cookies["dp_plink"] = r.cookies["dp_plink"].value
        r2 = c2.get(url, follow=True)
        self.assertEqual(r2.status_code, 200)
        self.assertContains(r2, "Jízdy —")
        self.assertContains(r2, self.driver_a.personal_number)
        from driver_portal.services.portal_driver_user import username_portal_driver_auto

        user = User.objects.get(username=username_portal_driver_auto(self.driver_a.pk))
        prof = UserAccessProfile.objects.get(user=user)
        self.assertEqual(prof.driver_profile_id, self.driver_a.pk)


class DriverPortalRidesTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="dp_staff2", password="pw", is_superuser=True)
        self.driver = DriverProfile.objects.create(personal_number="DP-300", last_name="Jetý")
        self.ridic_u = User.objects.create_user(username="dp_r2", password="pw")
        set_user_role(self.ridic_u, ROLE_RIDIC)
        UserAccessProfile.objects.update_or_create(
            user=self.ridic_u,
            defaults={"driver_profile_id": self.driver.pk},
        )
        self.today = date(2026, 5, 1)
        self.ride = _minimal_pruvodka(
            created_by=self.staff,
            driver=self.driver,
            drive_date=self.today,
        )

    def test_day_list_shows_assigned_ride(self):
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:day_list")
        r = c.get(url, {"date": self.today.isoformat()})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.ride.address.value)

    def test_anonymous_day_list_goes_to_driver_gate_not_system_login(self):
        c = Client()
        url = reverse("driver_portal:day_list")
        r = c.get(url)
        self.assertEqual(r.status_code, 302)
        gate = reverse("driver_portal:gate")
        self.assertTrue(r["Location"].split("?")[0].endswith(gate) or r["Location"] == gate)
        self.assertNotIn("/login/", r["Location"])

    def test_driver_logout_redirects_to_gate(self):
        c = Client()
        c.force_login(self.ridic_u)
        r = c.post(reverse("driver_portal:logout"))
        self.assertEqual(r.status_code, 302)
        loc = r["Location"].split("?")[0]
        self.assertTrue(loc.endswith(reverse("driver_portal:gate")))

    def test_ridic_dashboard_redirects_to_driver_portal(self):
        c = Client()
        c.force_login(self.ridic_u)
        r = c.get(reverse("core:dashboard"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse("driver_portal:day_list"))

    def test_ride_detail_404_for_foreign_ride(self):
        other_driver = DriverProfile.objects.create(personal_number="DP-999", last_name="Cizí")
        foreign = _minimal_pruvodka(created_by=self.staff, driver=other_driver, drive_date=self.today)
        c = Client()
        c.force_login(self.ridic_u)
        url = reverse("driver_portal:ride_detail", kwargs={"pk": foreign.pk})
        r = c.get(url)
        self.assertEqual(r.status_code, 404)

    def test_ride_detail_hides_second_container_when_activity_rule_off(self):
        from catalogs.models import ActivityCatalog, ActivityFieldKey, ActivityFieldMode, ActivityFieldRule

        act = ActivityCatalog.objects.create(name="DP-C1-only")
        ActivityFieldRule.objects.create(
            activity=act,
            field_key=ActivityFieldKey.CONTAINER_2,
            mode=ActivityFieldMode.OFF,
        )
        self.ride.activity = act
        self.ride.save(update_fields=["activity_id"])
        c = Client()
        c.force_login(self.ridic_u)
        r = c.get(reverse("driver_portal:ride_detail", kwargs={"pk": self.ride.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Číslo kontejneru (1)")
        self.assertNotContains(r, "Číslo kontejneru (2)")

    def test_non_ridic_gets_404_on_portal(self):
        z = User.objects.create_user(username="dp_z2", password="pw")
        set_user_role(z, ROLE_ZADAVATEL)
        c = Client()
        c.force_login(z)
        r = c.get(reverse("driver_portal:day_list"))
        self.assertEqual(r.status_code, 404)


class DriverPortalCatalogInviteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("dp_cat_admin", password="pw", is_superuser=True)
        self.driver = DriverProfile.objects.create(personal_number="DP-CAT-1", last_name="Katalog")
        self.other_driver = DriverProfile.objects.create(personal_number="DP-CAT-2", last_name="Jiný")

    def test_superuser_creates_invite_via_catalog_post(self):
        c = Client()
        c.force_login(self.admin)
        url = reverse("catalogs:driver_portal_invite_create", kwargs={"pk": self.driver.pk})
        r = c.post(url, {"invite_note": "poznámka"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(DriverPortalPairingToken.objects.filter(driver_id=self.driver.pk).count(), 1)
        t = DriverPortalPairingToken.objects.get(driver_id=self.driver.pk)
        self.assertEqual(t.note, "poznámka")

    def test_set_status_rejects_foreign_token_for_driver(self):
        token = DriverPortalPairingToken.objects.create(driver=self.driver)
        c = Client()
        c.force_login(self.admin)
        url = reverse(
            "catalogs:driver_portal_invite_set_status",
            kwargs={"pk": self.other_driver.pk, "token_pk": token.pk},
        )
        r = c.post(url, {"status": DriverPortalPairingToken.Status.REVOKED})
        self.assertEqual(r.status_code, 302)
        token.refresh_from_db()
        self.assertEqual(token.status, DriverPortalPairingToken.Status.ACTIVE)

    def test_superuser_can_unlink_portal_user_from_driver_card(self):
        ridic = User.objects.create_user(username="dp_unlink_ridic", password="pw")
        set_user_role(ridic, ROLE_RIDIC)
        UserAccessProfile.objects.update_or_create(
            user=ridic,
            defaults={"driver_profile_id": self.driver.pk},
        )
        c = Client()
        c.force_login(self.admin)
        url = reverse("catalogs:driver_portal_unlink_linked_user", kwargs={"pk": self.driver.pk})
        r = c.post(url)
        self.assertEqual(r.status_code, 302)
        prof = UserAccessProfile.objects.get(user=ridic)
        self.assertIsNone(prof.driver_profile_id)

    def test_driver_edit_renders_qr_data_uri_without_public_base_url(self):
        DriverPortalPairingToken.objects.create(driver=self.driver)
        c = Client()
        c.force_login(self.admin)
        r = c.get(reverse("catalogs:driver_edit", kwargs={"pk": self.driver.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "data:image/png;base64")
