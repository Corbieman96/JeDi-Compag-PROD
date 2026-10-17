"""Validace kontejneru při založení průvodky ze sběrného dvora (nova-jizda)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from catalogs.models import (
    ActivityCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile

from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.roles import set_user_role
from waste_docs.models import SvozYardDriverPlan
from waste_docs.services.yard_ride_container_validation import yard_ride_container_blocking_error


class YardRideContainerValidationTests(TestCase):
    def setUp(self):
        self.today = date(2036, 4, 1)
        self.name = NameCatalog.objects.create(value="Yard ride passport")
        self.ico = IcoCatalog.objects.create(value="77776666")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name, company_name="SD Passport", ico=self.ico
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_pruvodka = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="Odpad YR")
        self.suf = SuffixCatalog.objects.create(value="YR")
        self.vk_chain = VehicleKindCatalog.objects.create(name="Řetěz YR", shortcut="R")
        self.vk_hook = VehicleKindCatalog.objects.create(name="Hák YR", shortcut="H")
        self.activity = ActivityCatalog.objects.create(name="Průvodka YR")

        self.driver = DriverProfile.objects.create(personal_number="YR-1", last_name="Řidič")
        self.rz = VehicleRzCatalog.objects.create(value="8Y88888")
        prof = VehicleRzProfile.objects.create(rz=self.rz)
        prof.vehicle_kinds.add(self.vk_chain)

        SvozYardDriverPlan.objects.create(
            plan_date=self.today,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk_chain,
            sort_order=0,
        )

        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk_chain,
            yard_pruvodka_activity=self.activity,
            yard_svoz_display_label="Odpad YR",
        )

        ContainerPassport.objects.create(
            container_number="YR-614",
            vehicle_kind=self.vk_hook,
            color="—",
        )

        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_yr_val", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof_u, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)
        prof_u.sberny_dvur_subject = self.subject
        prof_u.save(update_fields=["sberny_dvur_subject_id"])

        self.client = Client()
        self.client.force_login(self.yard_user)
        self.ajax_url = reverse("waste_docs:yard_ride_validate_container")

    def test_blocking_error_when_passport_kind_mismatches_pair(self):
        err = yard_ride_container_blocking_error(
            subject=self.subject,
            pair=self.pair,
            container_number="YR-614",
            vehicle_rz_id=self.rz.pk,
            target_date=self.today,
        )
        self.assertIsNotNone(err)
        self.assertIn("YR-614", err)
        self.assertIn("pasport", err.casefold())

    def test_blocking_error_for_unknown_container(self):
        err = yard_ride_container_blocking_error(
            subject=self.subject,
            pair=self.pair,
            container_number="999-new",
            vehicle_rz_id=self.rz.pk,
            target_date=self.today,
        )
        self.assertIsNotNone(err)
        self.assertIn("není v číselníku pasportů", err)

    def test_blocking_error_for_multiple_containers(self):
        err = yard_ride_container_blocking_error(
            subject=self.subject,
            pair=self.pair,
            container_number="111, 222",
            vehicle_rz_id=self.rz.pk,
            target_date=self.today,
        )
        self.assertEqual(err, "Zadejte pouze jedno číslo kontejneru.")

    def test_no_error_when_passport_matches_pair_and_rz(self):
        ContainerPassport.objects.filter(container_number__iexact="YR-614").delete()
        ContainerPassport.objects.create(
            container_number="YR-614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        err = yard_ride_container_blocking_error(
            subject=self.subject,
            pair=self.pair,
            container_number="YR-614",
            vehicle_rz_id=self.rz.pk,
            target_date=self.today,
        )
        self.assertIsNone(err)

    def test_no_error_when_same_container_already_has_ride_today(self):
        """Průvodka ≠ svoz: stejný kontejner smí jet víckrát denně."""
        from catalogs.models import AddressCatalog, WasteCategoryCatalog, WasteCodeCatalog
        from waste_docs.models import Pruvodka

        ContainerPassport.objects.filter(container_number__iexact="YR-614").delete()
        ContainerPassport.objects.create(
            container_number="YR-614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        Pruvodka.objects.create(
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr YR multi"),
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCYRM"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCYRM"),
            suffix=self.suf,
            activity=self.activity,
            drive_date=self.today,
            container_number="YR-614",
            created_by=self.yard_user,
        )
        err = yard_ride_container_blocking_error(
            subject=self.subject,
            pair=self.pair,
            container_number="YR-614",
            vehicle_rz_id=self.rz.pk,
            target_date=self.today,
        )
        self.assertIsNone(err)

    def test_ajax_returns_error_for_mismatch(self):
        with patch.object(timezone, "localdate", return_value=self.today):
            r = self.client.get(
                self.ajax_url,
                {
                    "pair_pk": self.pair.pk,
                    "container": "YR-614",
                    "vehicle_rz_id": self.rz.pk,
                },
            )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data.get("errors"))

    def test_ajax_ok_when_passport_matches(self):
        ContainerPassport.objects.filter(container_number__iexact="YR-614").delete()
        ContainerPassport.objects.create(
            container_number="YR-614",
            vehicle_kind=self.vk_chain,
            color="—",
        )
        with patch.object(timezone, "localdate", return_value=self.today):
            r = self.client.get(
                self.ajax_url,
                {
                    "pair_pk": self.pair.pk,
                    "container": "YR-614",
                    "vehicle_rz_id": self.rz.pk,
                },
            )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_ajax_requires_vehicle_rz(self):
        with patch.object(timezone, "localdate", return_value=self.today):
            r = self.client.get(
                self.ajax_url,
                {"pair_pk": self.pair.pk, "container": "YR-614"},
            )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])
