"""Testy oprávnění generování PIO (export profilové šablony)."""

from django.contrib.auth.models import User
from django.test import TestCase

from catalogs.models import NameCatalog, NameSubjectProfile, SuffixCatalog, WasteTypeCatalog
from users.constants import ROLE_DISPECER, ROLE_RIDIC, ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.access import can_export_name_subject_pio_profile
from users.services.access_profile import get_access_profile
from users.services.role_permissions import role_default_export_pio_profile
from users.services.roles import set_user_role


class PioExportPermissionTests(TestCase):
    def _user(self, username: str, role: str) -> User:
        user = User.objects.create_user(username=username, password="x")
        set_user_role(user, role)
        return user

    def test_superuser_always_allowed(self):
        user = User.objects.create_user(username="su", password="x", is_superuser=True)
        self.assertTrue(can_export_name_subject_pio_profile(user))

    def test_inherit_dispecer_allowed_by_role_default(self):
        user = self._user("disp", ROLE_DISPECER)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.INHERIT
        prof.save()
        self.assertTrue(role_default_export_pio_profile(ROLE_DISPECER))
        self.assertTrue(can_export_name_subject_pio_profile(user))

    def test_inherit_zadavatel_allowed_by_role_default(self):
        user = self._user("zad", ROLE_ZADAVATEL)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.INHERIT
        prof.save()
        self.assertTrue(can_export_name_subject_pio_profile(user))

    def test_inherit_ridic_denied_by_role_default(self):
        user = self._user("rid", ROLE_RIDIC)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.INHERIT
        prof.save()
        self.assertFalse(role_default_export_pio_profile(ROLE_RIDIC))
        self.assertFalse(can_export_name_subject_pio_profile(user))

    def test_hide_overrides_allowed_role(self):
        user = self._user("disp2", ROLE_DISPECER)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.HIDE
        prof.save()
        self.assertFalse(can_export_name_subject_pio_profile(user))

    def test_show_overrides_denied_role(self):
        user = self._user("rid2", ROLE_RIDIC)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.SHOW
        prof.save()
        self.assertTrue(can_export_name_subject_pio_profile(user))


class PairPioDownloadPermissionTests(TestCase):
    def setUp(self):
        self.subject = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Subjekt PIO test"),
            company_name="Test subjekt",
        )
        self.waste = WasteTypeCatalog.objects.create(code="200301", value="Test odpad")
        self.suffix = SuffixCatalog.objects.create(value="K")
        self.pair = self.subject.waste_suffix_pairs.create(
            waste_type=self.waste,
            suffix=self.suffix,
            sort_order=1,
        )

    def test_pair_pio_download_forbidden_without_permission(self):
        from django.urls import reverse

        user = User.objects.create_user(username="noright", password="x")
        set_user_role(user, ROLE_DISPECER)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.HIDE
        prof.save()

        self.client.force_login(user)
        url = reverse(
            "catalogs:name_pair_pio_xlsx",
            args=[self.subject.pk, self.pair.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
