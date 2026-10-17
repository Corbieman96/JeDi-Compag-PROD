from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import IcoCatalog, NameCatalog, NameSubjectProfile
from users.services.sberny_dvur_subject_search import (
    search_sberny_dvur_subjects,
    sberny_dvur_subject_label,
)

User = get_user_model()


class SbernyDvurSubjectSearchServiceTests(TestCase):
    def setUp(self):
        self.ico = IcoCatalog.objects.create(value="12345678")
        self.name = NameCatalog.objects.create(value="Dvůr Testovice")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            ico=self.ico,
            company_name="Sběrný dvůr Testovice s.r.o.",
        )
        self.subject.is_collection_yard = True
        self.subject.save()

    def test_label_marks_collection_yard(self):
        label = sberny_dvur_subject_label(self.subject)
        self.assertIn("[SBĚR]", label)
        self.assertIn("12345678", label)
        self.assertIn("Dvůr Testovice", label)

    def test_search_by_company_name(self):
        rows = search_sberny_dvur_subjects("Testovice")
        ids = {row["subject_profile_id"] for row in rows}
        self.assertIn(self.subject.pk, ids)

    def test_search_short_query_returns_empty(self):
        self.assertEqual(search_sberny_dvur_subjects("T"), [])


class SbernyDvurSubjectSearchViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin_search", password="x")
        self.client = Client()

    def test_requires_admin(self):
        url = reverse("users:sberny_dvur_subject_search")
        res = self.client.get(url, {"q": "abc"})
        self.assertEqual(res.status_code, 302)

        self.client.force_login(self.admin)
        res = self.client.get(url, {"q": "abc"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(res.status_code, 200)
        payload = res.json()
        self.assertTrue(payload["ok"])
        self.assertIsInstance(payload["data"], list)
