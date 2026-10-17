from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalogs.models import IcoCatalog, NameCatalog, NameSubjectProfile
from core.models import AppSettings
from core.security import (
    SESSION_CREATED_AT_KEY,
    SESSION_LAST_ACTIVITY_KEY,
    SESSION_TOKEN_KEY,
    effective_session_idle_seconds,
    issue_security_session,
)
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.post_login import is_allowed_post_login_url, resolve_post_login_url
from users.services.roles import set_user_role


def _reset_app_settings(**defaults):
    AppSettings._cached_load.cache_clear()
    obj, _ = AppSettings.objects.get_or_create(pk=1)
    if defaults:
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save()
    AppSettings._cached_load.cache_clear()
    return obj


class SessionIdleSettingsTests(TestCase):
    def tearDown(self):
        AppSettings._cached_load.cache_clear()

    def test_effective_idle_uses_app_settings_minutes(self):
        _reset_app_settings(session_idle_timeout_minutes=45)
        self.assertEqual(effective_session_idle_seconds(), 45 * 60)

    def test_settings_form_shows_idle_field(self):
        User = get_user_model()
        admin = User.objects.create_user("idle_admin", password="pw", is_superuser=True)
        client = Client()
        client.force_login(admin)
        response = client.get(reverse("core:settings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "session_idle_timeout_minutes")
        self.assertContains(response, "Odhlásit po nečinnosti")


class YardPostLoginNextTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_next", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        name = NameCatalog.objects.create(value="SD Yard Next")
        ico = IcoCatalog.objects.create(value="11223344")
        self.subject = NameSubjectProfile.objects.create(
            name=name,
            company_name="SD Yard Next Co",
            ico=ico,
        )
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

    def test_sberny_dvur_next_is_allowed(self):
        hub = reverse("waste_docs:yard_hub")
        self.assertTrue(is_allowed_post_login_url(self.yard_user, hub))
        self.assertEqual(resolve_post_login_url(self.yard_user, hub), hub)

    def test_login_with_next_sberny_dvur_returns_there(self):
        client = Client()
        hub = reverse("waste_docs:yard_hub")
        resp = client.post(
            reverse("login"),
            {"username": "yard_next", "password": "pw", "next": hub},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("sberny-dvur", resp["Location"])


class SessionSecurityIdleRedirectTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("idle_user", password="pw", is_superuser=True)
        _reset_app_settings(session_idle_timeout_minutes=5)

    def tearDown(self):
        AppSettings._cached_load.cache_clear()

    def _expire_idle(self, client: Client):
        session = client.session
        issue_security_session(type("R", (), {"session": session})())
        session[SESSION_LAST_ACTIVITY_KEY] = 1
        session[SESSION_CREATED_AT_KEY] = 1
        session[SESSION_TOKEN_KEY] = session.get(SESSION_TOKEN_KEY) or "tok"
        session.save()

    def test_idle_redirect_includes_next(self):
        client = Client()
        client.force_login(self.user)
        self._expire_idle(client)
        with override_settings(SESSION_SECURITY_MAX_LIFETIME_SECONDS=10**9):
            response = client.get("/waste-docs/sberny-dvur/?x=1")
        self.assertEqual(response.status_code, 302)
        loc = response["Location"]
        self.assertTrue(
            loc.startswith("/accounts/login") or "/accounts/login/" in loc,
            msg=f"Expected absolute login path, got {loc!r}",
        )
        self.assertNotIn("/accounts/login/login", loc)
        self.assertFalse(loc.startswith("login?"), msg=f"Relative login Location: {loc!r}")
        self.assertIn("next=", loc)
        self.assertIn("sberny-dvur", loc)
        self.assertIn("reason=idle", loc)

    def test_login_url_for_session_expired_resolves_url_name(self):
        from core.security import login_url_for_session_expired

        url = login_url_for_session_expired("/waste-docs/sberny-dvur/?x=1")
        self.assertTrue(url.startswith("/accounts/login"))
        self.assertNotIn("/accounts/login/login", url)
        self.assertIn("reason=idle", url)
        self.assertIn("sberny-dvur", url)

    def test_idle_redirect_logs_session_for_yard_user(self):
        User = get_user_model()
        yard = User.objects.create_user("idle_yard_log", password="pw")
        set_user_role(yard, ROLE_SBERNY_DVUR)
        name = NameCatalog.objects.create(value="SD Idle Log")
        ico = IcoCatalog.objects.create(value="99887766")
        subject = NameSubjectProfile.objects.create(
            name=name,
            company_name="SD Idle Log Co",
            ico=ico,
        )
        prof, _ = UserAccessProfile.objects.get_or_create(user=yard)
        prof.sberny_dvur_subject = subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        client = Client()
        client.force_login(yard)
        self._expire_idle(client)
        with override_settings(SESSION_SECURITY_MAX_LIFETIME_SECONDS=10**9):
            response = client.get("/waste-docs/svoz-pozadavek/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("reason=idle", response["Location"])
        from waste_docs.models import YardSvozSubmitErrorLog

        entry = YardSvozSubmitErrorLog.objects.get(source="session")
        self.assertEqual(entry.subject_profile_id, subject.pk)
        self.assertEqual(entry.created_by_id, yard.pk)
        self.assertIn("nečinnosti", entry.message)
    def test_idle_ajax_returns_401_json(self):
        client = Client()
        client.force_login(self.user)
        self._expire_idle(client)
        with override_settings(SESSION_SECURITY_MAX_LIFETIME_SECONDS=10**9):
            response = client.get(
                "/waste-docs/sberny-dvur/",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("vypršelo", payload["error"].lower())

    def test_fresh_session_passes(self):
        client = Client()
        client.force_login(self.user)
        session = client.session
        issue_security_session(type("R", (), {"session": session})())
        session.save()
        resp = client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_session_keepalive_ok_for_authenticated(self):
        client = Client()
        client.force_login(self.user)
        session = client.session
        issue_security_session(type("R", (), {"session": session})())
        session.save()
        resp = client.get(reverse("core:session_keepalive"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_session_keepalive_requires_login(self):
        client = Client()
        resp = client.get(reverse("core:session_keepalive"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp["Location"])

    def test_dashboard_includes_idle_watch_script(self):
        client = Client()
        client.force_login(self.user)
        session = client.session
        issue_security_session(type("R", (), {"session": session})())
        session.save()
        resp = client.get(reverse("core:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "jedis-session-idle-config")
        self.assertContains(resp, "session_idle_watch.js")
