from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    ActivityFieldKey,
    ActivityFieldMode,
    ActivityFieldRule,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SubjectZpoSettings,
    SuffixCatalog,
    VehicleRzCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
    ZpoDocument,
)
from users.constants import ROLE_DISPECER
from users.services.roles import set_user_role
from waste_docs.models import Pruvodka
from waste_docs.services.zpo_instance_status import (
    clear_zpo_ensure_failure,
    explain_missing_zpo_instance,
    last_zpo_ensure_failure,
    record_zpo_ensure_failure,
    zpo_template_url_for_pruvodka,
)


class ExplainMissingZpoInstanceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("zpo_status", password="pw")
        self.name = NameCatalog.objects.create(value="Subjekt ZPO status")
        self.ico = IcoCatalog.objects.create(value="99887766")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.wt = WasteTypeCatalog.objects.create(code="160122", value="W status")
        self.suf = SuffixCatalog.objects.create(value="Konc status")
        self.activity = ActivityCatalog.objects.create(name="Výměna status")
        self.ride = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2026, 6, 26),
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr status"),
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCST"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOST"),
            suffix=self.suf,
            vehicle_rz=VehicleRzCatalog.objects.create(value="9S57595"),
            snd_cislo_listu="0000491-2026-6",
            container_number="",
            created_by=self.user,
        )

    def test_no_snd_returns_none(self):
        self.ride.snd_cislo_listu = ""
        self.ride.save(update_fields=("snd_cislo_listu",))
        self.assertIsNone(explain_missing_zpo_instance(self.ride))

    def test_missing_catalog_ids(self):
        self.ride.suffix_id = None
        self.ride.save(update_fields=("suffix_id",))
        reason = explain_missing_zpo_instance(self.ride)
        self.assertIn("subjekt", reason or "")

    def test_suppress_system_zpo_on_pair(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            suppress_system_zpo=True,
        )
        reason = explain_missing_zpo_instance(self.ride, pair=pair)
        self.assertIn("vypnuté systémové generování ZPO", reason or "")

    def test_system_generates_zpo_false_on_subject(self):
        zpo_settings = SubjectZpoSettings.objects.get(subject_profile=self.profile)
        zpo_settings.system_generates_zpo = False
        zpo_settings.save(update_fields=("system_generates_zpo",))
        reason = explain_missing_zpo_instance(self.ride)
        self.assertIn("u subjektu je vypnuté", reason or "")

    def test_activity_zpo_off(self):
        ActivityFieldRule.objects.create(
            activity=self.activity,
            field_key=ActivityFieldKey.ZPO,
            mode=ActivityFieldMode.OFF,
        )
        reason = explain_missing_zpo_instance(self.ride)
        self.assertIn("u činnosti je vypnuté", reason or "")

    def test_no_template_on_pair(self):
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
        )
        reason = explain_missing_zpo_instance(self.ride, pair=pair)
        self.assertIn("není přiřazen vzor ZPO", reason or "")

    def test_instance_ok_returns_none(self):
        self.ride.zpo_instance_file.save(
            "pruvodky/zpo_instance/test_ok.pdf",
            ContentFile(b"%PDF"),
            save=True,
        )
        self.ride.zpo_instance_for_snd = self.ride.snd_cislo_listu
        self.ride.save(update_fields=("zpo_instance_for_snd",))
        self.assertIsNone(explain_missing_zpo_instance(self.ride))

    def test_last_ensure_failure_in_explain(self):
        record_zpo_ensure_failure(self.ride.pk, "test chyba PDF")
        reason = explain_missing_zpo_instance(self.ride)
        self.assertIn("test chyba PDF", reason or "")
        clear_zpo_ensure_failure(self.ride.pk)
        self.assertEqual(last_zpo_ensure_failure(self.ride.pk), "")


class ZpoTemplateUrlTests(TestCase):
    def test_template_url_when_zpo_document_exists(self):
        zpo_doc = ZpoDocument.objects.create(label="Vzor test")
        zpo_doc.file.save("zpo/vzor_test.pdf", ContentFile(b"%PDF"), save=True)
        name = NameCatalog.objects.create(value="Subj ZPO url")
        profile = NameSubjectProfile.objects.create(name=name, ico=IcoCatalog.objects.create(value="11112222"))
        wt = WasteTypeCatalog.objects.create(code="990001", value="W url")
        suf = SuffixCatalog.objects.create(value="Suf url")
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=profile,
            waste_type=wt,
            suffix=suf,
            zpo=zpo_doc,
        )
        ride = Pruvodka.objects.create(
            name=name,
            ico=profile.ico,
            address=AddressCatalog.objects.create(value="Adr url"),
            waste_type=wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCURL"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOURL"),
            suffix=suf,
            drive_date=date(2026, 6, 26),
            vehicle_rz=VehicleRzCatalog.objects.create(value="1P11111"),
            snd_cislo_listu="0000999-2026-1",
            container_number="",
            created_by=get_user_model().objects.create_user("zpo_url", password="pw"),
        )
        url = zpo_template_url_for_pruvodka(ride, pair=pair)
        self.assertTrue(url)
        self.assertIn("zpo", url)


@patch("waste_docs.views.pruvodka_edit.city_from_coords", return_value="Česko")
class ZpoEditFlashTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("zpo_edit_flash", password="pw", is_superuser=True)
        self.name = NameCatalog.objects.create(value="Subjekt edit flash")
        self.ico = IcoCatalog.objects.create(value="55443322")
        self.wt = WasteTypeCatalog.objects.create(code="160122", value="W flash")
        self.suf = SuffixCatalog.objects.create(value="Konc flash")
        self.activity = ActivityCatalog.objects.create(name="Výměna flash")
        self.rz = VehicleRzCatalog.objects.create(value="8S88888")
        self.ride = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2026, 6, 26),
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr flash"),
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCFL"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOFL"),
            suffix=self.suf,
            vehicle_rz=self.rz,
            snd_cislo_listu="0000491-2026-6",
            container_number="",
            created_by=self.user,
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.edit_url = reverse("waste_docs:edit", kwargs={"pk": self.ride.pk})

    def _post_data(self) -> dict[str, str]:
        return {
            "activity": str(self.activity.pk),
            "drive_date": self.ride.drive_date.strftime("%Y-%m-%d"),
            "repeat_count": "1",
            "name": str(self.ride.name_id),
            "ico": str(self.ride.ico_id),
            "waste_type": str(self.ride.waste_type_id),
            "suffix": str(self.ride.suffix_id),
            "vehicle_rz": str(self.ride.vehicle_rz_id),
            "container_number": "",
            "container_number_2": "",
            "contact_phone": "",
            "contract_number": "",
            "contact_note": "",
            "ico_lookup": self.name.value,
            "skip_follow_up": "",
            "follow_up_parent": "",
            "fulfillment_address_value": self.ride.address.value,
        }

    @patch("waste_docs.views.pruvodka_edit.explain_missing_zpo_instance", return_value="u subjektu je vypnuté systémové generování ZPO")
    @patch("waste_docs.views.pruvodka_edit.display_zpo_file_for_pruvodka", return_value=None)
    @patch("waste_docs.views.pruvodka_edit.ensure_zpo_instance_for_pruvodka_pk", return_value=False)
    @patch("waste_docs.views.pruvodka_edit.system_may_generate_zpo_instance", return_value=True)
    def test_edit_save_shows_zpo_warning(self, *_mocks, _mock_city):
        response = self.client.post(self.edit_url, self._post_data())
        self.assertRedirects(response, reverse("waste_docs:detail", kwargs={"pk": self.ride.pk}))
        msgs = [str(m) for m in get_messages(response.wsgi_request)]
        self.assertTrue(any("ZPO s číslem listu se nepodařilo připravit" in m for m in msgs))
        self.assertTrue(any("u subjektu je vypnuté" in m for m in msgs))


class ZpoDetailContextTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.dispecer = User.objects.create_user("zpo_detail_ctx", password="pw")
        set_user_role(self.dispecer, ROLE_DISPECER)
        self.name = NameCatalog.objects.create(value="Subjekt detail ctx")
        self.ico = IcoCatalog.objects.create(value="66778899")
        self.profile = NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.wt = WasteTypeCatalog.objects.create(code="160122", value="W ctx")
        self.suf = SuffixCatalog.objects.create(value="Konc ctx")
        zpo_doc = ZpoDocument.objects.create(label="Vzor ctx")
        zpo_doc.file.save("zpo/vzor_ctx.pdf", ContentFile(b"%PDF"), save=True)
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt,
            suffix=self.suf,
            zpo=zpo_doc,
            suppress_system_zpo=True,
        )
        zpo_settings = SubjectZpoSettings.objects.get(subject_profile=self.profile)
        zpo_settings.system_generates_zpo = True
        zpo_settings.save(update_fields=("system_generates_zpo",))
        self.activity = ActivityCatalog.objects.create(name="Výměna ctx")
        self.ride = Pruvodka.objects.create(
            activity=self.activity,
            drive_date=date(2026, 6, 26),
            name=self.name,
            ico=self.ico,
            address=AddressCatalog.objects.create(value="Adr ctx"),
            waste_type=self.wt,
            waste_code=WasteCodeCatalog.objects.create(value="WCCTX"),
            waste_category=WasteCategoryCatalog.objects.create(value="KOCTX"),
            suffix=self.suf,
            vehicle_rz=VehicleRzCatalog.objects.create(value="7S77777"),
            snd_cislo_listu="0000491-2026-6",
            container_number="",
            created_by=self.dispecer,
        )
        self.client = Client()
        self.client.force_login(self.dispecer)

    @patch("waste_docs.views.pruvodka_pages.detail.ensure_zpo_instance_for_pruvodka_pk")
    @patch("waste_docs.views.pruvodka_pages.detail.system_may_generate_zpo_instance", return_value=False)
    def test_detail_shows_template_when_generation_blocked(self, _mock_may, _mock_ensure):
        url = reverse("waste_docs:detail", kwargs={"pk": self.ride.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vzor ZPO")
        self.assertContains(response, "vypnuté systémové generování ZPO")
