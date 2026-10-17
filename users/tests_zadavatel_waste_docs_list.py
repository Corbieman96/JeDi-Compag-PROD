"""Přístup role Zadavatel k seznamu jízd /waste-docs/."""

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
from users.constants import ROLE_KONTROLOR, ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.nav_visibility import effective_show_pruvodky_nav
from users.services.roles import set_user_role
from users.services.waste_doc_permissions import can_create_pruvodka
from waste_docs.models import Pruvodka


def _minimal_pruvodka(*, created_by, drive_date=None):
    name = NameCatalog.objects.create(value=f"Sub {created_by.username}")
    return Pruvodka.objects.create(
        drive_date=drive_date or timezone.localdate(),
        name=name,
        ico=IcoCatalog.objects.create(value=f"I{created_by.pk:07d}"[:8]),
        address=AddressCatalog.objects.create(value=f"Test {created_by.pk}, 60200 Brno"),
        waste_type=WasteTypeCatalog.objects.create(
            code=f"99{created_by.pk:04d}"[-6:], value=f"Wt {created_by.username}"
        ),
        waste_code=WasteCodeCatalog.objects.create(value=f"WC{created_by.pk}"),
        waste_category=WasteCategoryCatalog.objects.create(value=f"KC{created_by.pk}"),
        suffix=SuffixCatalog.objects.create(value=f"S{created_by.pk}"),
        vehicle_rz=VehicleRzCatalog.objects.create(value=f"RZ{created_by.pk}"),
        container_number="",
        created_by=created_by,
    )


@override_settings(ROOT_URLCONF="config.urls")
class ZadavatelWasteDocsListAccessTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("zad_list", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.other = User.objects.create_user("other_list", password="pw")
        set_user_role(self.other, ROLE_ZADAVATEL)
        self.client = Client()

    def test_default_zadavatel_nav_hidden(self):
        self.assertFalse(effective_show_pruvodky_nav(self.zadavatel))

    def test_zadavatel_without_access_gets_404_on_list(self):
        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:list"))
        self.assertEqual(resp.status_code, 404)

    def test_zadavatel_show_override_sees_all_rides(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])

        own = _minimal_pruvodka(created_by=self.zadavatel)
        other_ride = _minimal_pruvodka(created_by=self.other)

        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:list"), {"all": "1"})
        self.assertEqual(resp.status_code, 200)
        ids = {p.pk for p in resp.context["page_obj"].object_list}
        self.assertIn(own.pk, ids)
        self.assertIn(other_ride.pk, ids)

    def test_kontrolor_with_list_access_sees_other_users_rides(self):
        User = get_user_model()
        kontrolor = User.objects.create_user("kontr_list", password="pw")
        set_user_role(kontrolor, ROLE_KONTROLOR)
        prof = get_access_profile(kontrolor)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])

        other_ride = _minimal_pruvodka(created_by=self.other)
        self.client.force_login(kontrolor)
        resp = self.client.get(reverse("waste_docs:list"), {"all": "1"})
        self.assertEqual(resp.status_code, 200)
        ids = {p.pk for p in resp.context["page_obj"].object_list}
        self.assertIn(other_ride.pk, ids)

    def test_zadavatel_can_open_detail_of_other_users_ride(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])

        other_ride = _minimal_pruvodka(created_by=self.other)
        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:detail", args=[other_ride.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["ride_detail_read_only"])

    def test_zadavatel_detail_read_only_without_edit_button(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])

        ride = _minimal_pruvodka(created_by=self.zadavatel)
        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:detail", args=[ride.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["can_edit_waste_doc"])
        self.assertFalse(resp.context["can_create_waste_doc"])
        self.assertTrue(resp.context["ride_detail_read_only"])
        self.assertNotContains(resp, "Upravit jízdu")
        self.assertNotContains(resp, "Nová jízda")
        self.assertNotContains(resp, "Vygenerovat průvodku")

    def test_zadavatel_cannot_edit_own_ride(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])

        ride = _minimal_pruvodka(created_by=self.zadavatel)
        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:edit", args=[ride.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_zadavatel_cannot_create_ride(self):
        prof = get_access_profile(self.zadavatel)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_pruvodky"])
        self.assertFalse(can_create_pruvodka(self.zadavatel))

        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:create"))
        self.assertEqual(resp.status_code, 302)

    def test_app_settings_enables_nav_for_zadavatel_role(self):
        settings = AppSettings.load()
        settings.role_nav_defaults = {
            ROLE_ZADAVATEL: {
                "dashboard": True,
                "pruvodky": True,
                "customer_requests": True,
                "invoice_queue": False,
                "catalogs": True,
                "settings": False,
                "address_data": False,
                "reports": False,
            }
        }
        settings.save(update_fields=["role_nav_defaults"])
        self.assertTrue(effective_show_pruvodky_nav(self.zadavatel))

        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:list"))
        self.assertEqual(resp.status_code, 200)

    def test_zadavatel_without_access_gets_404_on_detail_of_own_ride(self):
        ride = _minimal_pruvodka(created_by=self.zadavatel)
        self.client.force_login(self.zadavatel)
        resp = self.client.get(reverse("waste_docs:detail", args=[ride.pk]))
        self.assertEqual(resp.status_code, 404)
