"""API nápovědy otevřených návazností subjektu — dynamicky dle číselníku činností."""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from waste_docs.models import Pruvodka


class SubjectOpenFollowUpsApiTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("open_fu", password="pw", is_superuser=True)
        self.client = Client()
        self.client.login(username="open_fu", password="pw")
        self.url = reverse("waste_docs:subject_open_follow_ups")

        self.name = NameCatalog.objects.create(value="Subjekt open fu")
        self.ico = IcoCatalog.objects.create(value="55667788")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Ulice, 2, Město")
        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W open fu")
        self.suf = SuffixCatalog.objects.create(value="B open")
        wc = WasteCodeCatalog.objects.create(value="20 03 01")
        wcat = WasteCategoryCatalog.objects.create(value="Ostatní")

        self.follow_activity = ActivityCatalog.objects.create(name="Stažení open fu")
        self.parent_activity = ActivityCatalog.objects.create(name="Přistavení open fu")
        self.parent_activity.follow_up_activity = self.follow_activity
        self.parent_activity.save()

        self.vymena_activity = ActivityCatalog.objects.create(name="Výměna open fu")

        self._wc = wc
        self._wcat = wcat

    def _create_open(self, *, activity: ActivityCatalog, suffix: str = "") -> Pruvodka:
        return Pruvodka.objects.create(
            activity=activity,
            drive_date=date(2026, 3, 1),
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.wt,
            waste_code=self._wc,
            waste_category=self._wcat,
            suffix=self.suf,
            follow_up_open=True,
            created_by=self.user,
        )

    def _get_items(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return response.json()["items"]

    def test_vymena_without_follow_up_option_excluded(self):
        stale = self._create_open(activity=self.vymena_activity)
        items = self._get_items(name_id=self.name.pk)
        pks = {it["pk"] for it in items}
        self.assertNotIn(stale.pk, pks)

    def test_vymena_reappears_when_follow_up_enabled(self):
        stale = self._create_open(activity=self.vymena_activity)
        self.vymena_activity.follow_up_activity = self.follow_activity
        self.vymena_activity.save()

        items = self._get_items(
            name_id=self.name.pk,
            activity_id=self.follow_activity.pk,
        )
        pks = {it["pk"] for it in items}
        self.assertIn(stale.pk, pks)

    def test_parent_with_follow_up_included(self):
        open_parent = self._create_open(activity=self.parent_activity)
        items = self._get_items(
            name_id=self.name.pk,
            activity_id=self.follow_activity.pk,
        )
        pks = {it["pk"] for it in items}
        self.assertIn(open_parent.pk, pks)

    def test_activity_id_filters_to_predecessors_only(self):
        open_parent = self._create_open(activity=self.parent_activity)
        stale_vymena = self._create_open(activity=self.vymena_activity)

        items = self._get_items(
            name_id=self.name.pk,
            activity_id=self.follow_activity.pk,
        )
        pks = {it["pk"] for it in items}
        self.assertIn(open_parent.pk, pks)
        self.assertNotIn(stale_vymena.pk, pks)

    def test_no_predecessors_for_activity_returns_empty(self):
        self._create_open(activity=self.parent_activity)
        items = self._get_items(
            name_id=self.name.pk,
            activity_id=self.vymena_activity.pk,
        )
        self.assertEqual(items, [])
