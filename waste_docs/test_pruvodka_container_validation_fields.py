"""Validace pasportu u nové průvodky — chyby musí jít na existující pole formuláře."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    ActivityCatalog,
    AddressCatalog,
    ContainerPassport,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)
from core.models import AppSettings
from catalogs.models.activity_field_rule import ActivityFieldKey, ActivityFieldMode, ActivityFieldRule
from catalogs.models.vehicle_rz import VehicleKindCatalog, VehicleRzProfile
from waste_docs.forms import PruvodkaForm
from waste_docs.models import Pruvodka


class PruvodkaContainerValidationFieldTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("cnt_val", password="x")

        self.name = NameCatalog.objects.create(value="Subjekt cnt val")
        self.ico = IcoCatalog.objects.create(value="12345670")
        self.subject = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        adr = AddressCatalog.objects.create(value="Ulice, 1, Město")
        ap = self.subject.address_profile
        ap.fulfillment_address = adr
        ap.save()

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W cnt")
        self.suf = SuffixCatalog.objects.create(value="S cnt")
        self.vk = VehicleKindCatalog.objects.create(name="Vk cnt", shortcut="Vc", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Act cnt")
        self.activity.vehicle_kinds.add(self.vk)
        ActivityFieldRule.objects.filter(activity=self.activity).delete()
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.CONTAINER_1,
            mode=ActivityFieldMode.REQUIRED,
        )

        self.rz = VehicleRzCatalog.objects.create(value="RZCNT01")
        self.prof = VehicleRzProfile.objects.create(rz=self.rz)
        self.prof.vehicle_kinds.add(self.vk)
        self.driver = DriverProfile.objects.create(personal_number="CNT-D1", last_name="Cnt")

        self.passport = ContainerPassport.objects.create(
            container_number="230",
            vehicle_kind=self.vk,
        )

        wc = WasteCodeCatalog.objects.create(value="20 03 01")
        wcat = WasteCategoryCatalog.objects.create(value="Nebezpečný")
        self.existing = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2035, 3, 1),
            name=self.name,
            ico=self.ico,
            address=adr,
            waste_type=self.wt,
            waste_code=wc,
            waste_category=wcat,
            suffix=self.suf,
            vehicle_rz=self.rz,
            driver=self.driver,
            container_number="230",
            container_passport=self.passport,
            created_by=self.user,
        )

    def test_duplicate_container_error_on_create_form_uses_container_number(self):
        """U nové jízdy není pole container_passport — chyba duplicity musí jít na container_number."""
        data = {
            "activity": str(self.activity.pk),
            "drive_date": "2035-03-02",
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz.pk),
            "container_number": "230",
            "container_number_2": "",
            "fulfillment_address_value": "Ulice, 1, Město",
            "repeat_count": "1",
        }
        form = PruvodkaForm(data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("container_number", form.errors)
        self.assertNotIn("container_passport", form.errors)

    def test_duplicate_check_can_be_disabled_in_app_settings(self):
        settings_obj = AppSettings.load()
        settings_obj.enforce_container_passport_move_check = False
        settings_obj.save(update_fields=["enforce_container_passport_move_check"])
        data = {
            "activity": str(self.activity.pk),
            "drive_date": "2035-03-02",
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz.pk),
            "container_number": "230",
            "container_number_2": "",
            "fulfillment_address_value": "Ulice, 1, Město",
            "repeat_count": "1",
        }
        form = PruvodkaForm(data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def _edit_form_data(self, **overrides):
        data = {
            "activity": str(self.activity.pk),
            "drive_date": "2035-03-01",
            "driver": str(self.driver.pk),
            "waste_type": str(self.wt.pk),
            "name": str(self.name.pk),
            "ico": str(self.ico.pk),
            "suffix": str(self.suf.pk),
            "vehicle_rz": str(self.rz.pk),
            "container_number": "230",
            "container_number_2": "",
            "container_passport": str(self.passport.pk),
            "fulfillment_address_value": "Ulice, 1, Město",
            "repeat_count": "1",
        }
        data.update(overrides)
        return data

    def test_edit_same_ride_change_vehicle_rz_allowed(self):
        """Úprava jízdy se stejným kontejnerem a změnou RZ nesmí hlásit duplicitu vůči sobě."""
        rz2 = VehicleRzCatalog.objects.create(value="RZCNT02")
        prof2 = VehicleRzProfile.objects.create(rz=rz2)
        prof2.vehicle_kinds.add(self.vk)
        data = self._edit_form_data(vehicle_rz=str(rz2.pk))
        form = PruvodkaForm(data, instance=self.existing, is_edit=True, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_allowed_when_follow_up_child_shares_container(self):
        """Rodič a navazující dítě mohou sdílet kontejner — edit rodiče nesmí blokovat."""
        wc = WasteCodeCatalog.objects.get(value="20 03 01")
        wcat = WasteCategoryCatalog.objects.get(value="Nebezpečný")
        child = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2035, 3, 2),
            name=self.name,
            ico=self.ico,
            address=self.existing.address,
            waste_type=self.wt,
            waste_code=wc,
            waste_category=wcat,
            suffix=self.suf,
            vehicle_rz=self.rz,
            driver=self.driver,
            container_number="230",
            container_passport=self.passport,
            follow_up_parent=self.existing,
            created_by=self.user,
        )
        self.assertIsNotNone(child.pk)
        data = self._edit_form_data()
        form = PruvodkaForm(data, instance=self.existing, is_edit=True, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_edit_unchanged_container_allowed_when_other_ride_has_same_container(self):
        """Edit bez změny kontejneru — duplicita u jiné jízdy neblokuje uložení (např. změna RZ)."""
        wc = WasteCodeCatalog.objects.get(value="20 03 01")
        wcat = WasteCategoryCatalog.objects.get(value="Nebezpečný")
        adr = AddressCatalog.objects.get(value="Ulice, 1, Město")
        Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2035, 2, 15),
            name=self.name,
            ico=self.ico,
            address=adr,
            waste_type=self.wt,
            waste_code=wc,
            waste_category=wcat,
            suffix=self.suf,
            vehicle_rz=self.rz,
            driver=self.driver,
            container_number="230",
            container_passport=self.passport,
            snd_cislo_listu="0000245-2026-1",
            created_by=self.user,
        )
        rz2 = VehicleRzCatalog.objects.create(value="RZCNT03")
        prof3 = VehicleRzProfile.objects.create(rz=rz2)
        prof3.vehicle_kinds.add(self.vk)
        data = self._edit_form_data(vehicle_rz=str(rz2.pk))
        form = PruvodkaForm(data, instance=self.existing, is_edit=True, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
