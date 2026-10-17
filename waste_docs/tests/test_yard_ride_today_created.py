"""DneĹˇnĂ­ prĹŻvodky pod Ĺ™Ăˇdkem matice na nova-jizda."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleRzProfile
from users.constants import ROLE_SBERNY_DVUR
from users.models import UserAccessProfile
from users.services.nav_visibility import effective_show_pruvodky_nav
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka, SvozYardDriverPlan
from waste_docs.services.yard_ride_today_created import yard_rides_today_by_pair


class YardRideTodayCreatedTests(TestCase):
    def setUp(self):
        self.today = date(2036, 5, 20)
        User = get_user_model()
        self.yard_user = User.objects.create_user("yard_today", password="pw")
        set_user_role(self.yard_user, ROLE_SBERNY_DVUR)
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.yard_user)

        self.name = NameCatalog.objects.create(value="Today rides yard")
        self.ico = IcoCatalog.objects.create(value="66665555")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="SD Today",
            ico=self.ico,
        )
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.yard_allow_pruvodka = True
        self.subject.yard_settings.save()
        prof.sberny_dvur_subject = self.subject
        prof.save(update_fields=["sberny_dvur_subject_id"])

        adr = AddressCatalog.objects.create(value="Ulice 2, MÄ›sto")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200320", value="O today")
        self.suf = SuffixCatalog.objects.create(value="TD")
        self.vk = VehicleKindCatalog.objects.create(name="HĂˇk today", shortcut="H")
        self.activity = ActivityCatalog.objects.create(name="PrĹŻvodka today")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

        self.rz = VehicleRzCatalog.objects.create(value="9T99999")
        prof_rz = VehicleRzProfile.objects.create(rz=self.rz)
        prof_rz.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="TD-1", last_name="Today")

        SvozYardDriverPlan.objects.create(
            plan_date=self.today,
            subject_profile=self.subject,
            driver=self.driver,
            vehicle_rz=self.rz,
            row_kind=SvozYardDriverPlan.RowKind.STANDARD,
            vehicle_kind=self.vk,
            sort_order=0,
        )

        self.container_number = "CNT-TODAY-1"
        from catalogs.models import ContainerPassport

        ContainerPassport.objects.create(
            container_number=self.container_number,
            vehicle_kind=self.vk,
            color="â€”",
        )

        self.url = reverse("waste_docs:yard_ride_create")
        self.client = Client()
        self.client.force_login(self.yard_user)
        import tempfile
        self.tmp_media = tempfile.mkdtemp()

    def _create_ride(self, *, with_file: bool = True) -> Pruvodka:
        ride = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=self.today,
            driver=self.driver,
            vehicle_rz=self.rz,
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCTD"),
            waste_category=WasteCategoryCatalog.objects.create(value="KCTD"),
            suffix=self.suf,
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr TD"),
            container_number=self.container_number,
            vehicle_rz_snapshot=self.rz.value,
            driver_snapshot="Today",
            snd_cislo_listu="0000100-2036-1",
            source_waste_suffix_pair=self.pair,
            created_by=self.yard_user,
        )
        if with_file:
            ride.generated_file.save("today_ride.xlsx", ContentFile(b"PK"), save=True)
        return ride

    def test_service_maps_ride_by_source_pair(self):
        ride = self._create_ride()
        mapped = yard_rides_today_by_pair(
            self.subject, [self.pair], self.today, created_by=self.yard_user
        )
        self.assertEqual(len(mapped[self.pair.pk]), 1)
        self.assertEqual(mapped[self.pair.pk][0]["pk"], ride.pk)
        self.assertTrue(mapped[self.pair.pk][0]["has_pdf"])

    def test_service_ignores_other_user_rides(self):
        User = get_user_model()
        other = User.objects.create_user("other_yard", password="pw")
        self._create_ride()
        mapped = yard_rides_today_by_pair(
            self.subject, [self.pair], self.today, created_by=other
        )
        self.assertEqual(mapped[self.pair.pk], [])

    def test_service_ignores_rides_without_source_pair(self):
        ride = self._create_ride()
        ride.source_waste_suffix_pair = None
        ride.save(update_fields=["source_waste_suffix_pair"])
        mapped = yard_rides_today_by_pair(
            self.subject, [self.pair], self.today, created_by=self.yard_user
        )
        self.assertEqual(mapped[self.pair.pk], [])

    def test_get_shows_pdf_link_under_pair(self):
        self._create_ride()
        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.get(self.url)
        self.assertContains(response, "yard-today-rides")
        self.assertContains(response, "Vaše dnes založené")
        self.assertContains(response, "PDF")
        self.assertContains(response, self.container_number)
        self.assertContains(
            response,
            reverse("waste_docs:ride_pruvodka_pdf", kwargs={"pk": Pruvodka.objects.get().pk}),
        )
        self.assertContains(response, 'target="_blank"')


    @patch("waste_docs.views.pruvodka_pages.detail.convert_xlsx_to_pdf")
    def test_yard_user_can_open_pdf_without_pruvodky_nav(self, mock_convert):
        prof = UserAccessProfile.objects.get(user=self.yard_user)
        prof.nav_pruvodky = UserAccessProfile.NavOverride.HIDE
        prof.save(update_fields=["nav_pruvodky"])
        self.assertFalse(effective_show_pruvodky_nav(self.yard_user))

        ride = self._create_ride()
        pdf_path = Path(self.tmp_media) / "test_ride.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 test")
        mock_convert.return_value = pdf_path

        url = reverse("waste_docs:ride_pruvodka_pdf", kwargs={"pk": ride.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_post_sets_source_waste_suffix_pair(self):
        data = {
            "pair_pk": [str(self.pair.pk)],
            f"vehicle_rz_{self.pair.pk}": str(self.rz.pk),
            f"container_{self.pair.pk}": self.container_number,
            f"driver_{self.pair.pk}": str(self.driver.pk),
        }
        with patch.object(timezone, "localdate", return_value=self.today):
            response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        ride = Pruvodka.objects.get()
        self.assertEqual(ride.source_waste_suffix_pair_id, self.pair.pk)

