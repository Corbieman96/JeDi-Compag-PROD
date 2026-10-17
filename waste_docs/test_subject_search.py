"""Vyhledávání subjektu F/P pro formulář nové jízdy."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import IcoCatalog, NameCatalog, NameSubjectProfile
from users.models import UserAccessProfile


class SubjectSearchTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="subject_search", password="x")
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])
        self.client = Client()
        self.client.force_login(self.user)

        self.name = NameCatalog.objects.create(value="Firma test IČO s.r.o.")
        self.ico = IcoCatalog.objects.create(value="10700854")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            ico=self.ico,
            company_name="Firma test IČO s.r.o.",
        )

    def test_subject_search_by_ico(self):
        url = reverse("waste_docs:subject_search")
        response = self.client.get(url, {"q": "10700854"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        ids = [row["subject_profile_id"] for row in payload["data"]]
        self.assertIn(self.subject.pk, ids)
        hit = next(r for r in payload["data"] if r["subject_profile_id"] == self.subject.pk)
        self.assertEqual(hit["ico"], "10700854")

    def test_subject_search_profile_without_ico_not_found_by_ico(self):
        ico_orphan = IcoCatalog.objects.create(value="10101010")
        name_only = NameCatalog.objects.create(value="Subjekt bez IČO v profilu")
        NameSubjectProfile.objects.create(name=name_only, company_name="Subjekt bez IČO v profilu")
        url = reverse("waste_docs:subject_search")
        response = self.client.get(url, {"q": "10101010"})
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"], [])
        self.assertTrue(ico_orphan.pk)
