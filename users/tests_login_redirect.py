from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import AppSettings
from users.constants import ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.roles import set_user_role


@override_settings(ROOT_URLCONF="config.urls")
class ZadavatelLoginRedirectTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("zad_login", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.client = Client()

    def test_login_redirects_off_login_page(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "zad_login", "password": "pw"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/accounts/login", resp["Location"])

        follow = self.client.get(resp["Location"], follow=True)
        self.assertEqual(follow.status_code, 200)
        self.assertNotContains(follow, 'class="login-form"')
        self.assertContains(follow, "Odhlásit")

    def test_login_with_next_waste_docs_denied_redirects_to_požadavky(self):
        resp = self.client.post(
            reverse("login"),
            {"username": "zad_login", "password": "pw", "next": reverse("waste_docs:list")},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("customer", resp["Location"].lower())
        follow = self.client.get(resp["Location"], follow=True)
        self.assertEqual(follow.status_code, 200)
        self.assertNotContains(follow, 'class="login-form"')
        self.assertContains(follow, "Odhlásit")

    def test_login_with_pruvodky_nav_goes_to_list(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.nav_customer_requests = UserAccessProfile.NavOverride.HIDE
        prof.save(update_fields=["nav_pruvodky", "nav_customer_requests"])

        resp = self.client.post(
            reverse("login"),
            {"username": "zad_login", "password": "pw"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("waste-docs", resp["Location"])
        follow = self.client.get(resp["Location"], follow=True)
        self.assertEqual(follow.status_code, 200)

    def test_login_when_only_customer_requests_nav(self):
        settings = AppSettings.load()
        settings.role_nav_defaults = {
            ROLE_ZADAVATEL: {
                "dashboard": False,
                "pruvodky": False,
                "customer_requests": True,
                "invoice_queue": False,
                "catalogs": False,
                "settings": False,
                "address_data": False,
                "reports": False,
            }
        }
        settings.save(update_fields=["role_nav_defaults"])

        resp = self.client.post(
            reverse("login"),
            {"username": "zad_login", "password": "pw"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("customer", resp["Location"].lower())

        follow = self.client.get(resp["Location"], follow=True)
        self.assertEqual(follow.status_code, 200)
        self.assertNotContains(follow, 'class="login-form"')

    def test_login_with_next_dashboard_denied_redirects_to_požadavky(self):
        settings = AppSettings.load()
        settings.role_nav_defaults = {
            ROLE_ZADAVATEL: {
                "dashboard": False,
                "pruvodky": False,
                "customer_requests": True,
                "invoice_queue": False,
                "catalogs": False,
                "settings": False,
                "address_data": False,
                "reports": False,
            }
        }
        settings.save(update_fields=["role_nav_defaults"])

        resp = self.client.post(
            reverse("login"),
            {"username": "zad_login", "password": "pw", "next": "/"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("customer", resp["Location"].lower())
