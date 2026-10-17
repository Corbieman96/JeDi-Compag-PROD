"""Výchozí 90denní rozsah seznamu jízd bez explicitního GET."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from core.models import AppSettings
from waste_docs.models import Pruvodka


@override_settings(ROOT_URLCONF="config.urls")
class PruvodkaListDefaultRangeTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("list_range", password="pw", is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

        settings = AppSettings.load()
        settings.waste_docs_default_range_days = 90
        settings.save()

        self.name = NameCatalog.objects.create(value="Sub range")
        common = dict(
            name=self.name,
            ico=IcoCatalog.objects.create(value="11111111"),
            address=AddressCatalog.objects.create(value="Test 1, 60200 Brno"),
            waste_type=WasteTypeCatalog.objects.create(code="990098", value="Wr"),
            waste_code=WasteCodeCatalog.objects.create(value="WCWR"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCWR"),
            suffix=SuffixCatalog.objects.create(value="SWR"),
            vehicle_rz=VehicleRzCatalog.objects.create(value="RZRANGE"),
            container_number="",
            created_by=self.user,
        )

        today = timezone.localdate()
        self.recent = Pruvodka.objects.create(drive_date=today - timedelta(days=10), **common)
        self.old = Pruvodka.objects.create(drive_date=today - timedelta(days=120), **common)

    def test_default_list_excludes_rides_older_than_90_days(self):
        resp = self.client.get(reverse("waste_docs:list"))
        self.assertEqual(resp.status_code, 200)
        ids = {p.pk for p in resp.context["page_obj"].object_list}
        self.assertIn(self.recent.pk, ids)
        self.assertNotIn(self.old.pk, ids)

    def test_all_param_shows_old_rides(self):
        resp = self.client.get(reverse("waste_docs:list"), {"all": "1"})
        self.assertEqual(resp.status_code, 200)
        ids = {p.pk for p in resp.context["page_obj"].object_list}
        self.assertIn(self.recent.pk, ids)
        self.assertIn(self.old.pk, ids)
