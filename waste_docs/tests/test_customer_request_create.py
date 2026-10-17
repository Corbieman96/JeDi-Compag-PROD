"""POST vytvoření zákaznického požadavku z /customer-requests/new/."""

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
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.roles import set_user_role
from waste_docs.forms import CustomerRequestForm
from waste_docs.services.customer_request_form.client_config import customer_request_form_client_config


class CustomerRequestCreateTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("cr_create_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.day = date(2038, 6, 15)

        self.name = NameCatalog.objects.create(value="Subjekt create CR")
        self.ico = IcoCatalog.objects.create(value="99887766")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Create ulice, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200301", value="W create")
        self.suf = SuffixCatalog.objects.create(value="KV")
        self.vk = VehicleKindCatalog.objects.create(name="Hák cr", shortcut="Hc", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz create", visible_for_submitter=True)

        meta = waste_type_combo_metadata()
        self.waste_label = meta[str(self.wt.pk)]["label"]

    def _base_post_data(self, **overrides):
        data = {
            "name_existing": str(self.name.pk),
            "name_lookup": self.name.value,
            "activity": str(self.activity.pk),
            "vehicle_kind": str(self.vk.pk),
            "waste_type": str(self.wt.pk),
            "waste_type_lookup": self.waste_label,
            "suffix": str(self.suf.pk),
            "target_date": self.day.isoformat(),
            "address_value": self.address.value,
            "facility_address_value": "",
            "contact_phone": "",
            "contact_note": "",
            "note": "",
            "has_follow_up": "",
            "follow_up_activity": "",
            "follow_up_target_date": "",
            "is_recurring": "",
            "requires_advance_invoice": "",
        }
        data.update(overrides)
        return data

    def test_post_create_redirects_and_sets_dispatcher_review(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.post(
            reverse("waste_docs:customer_request_create"),
            self._base_post_data(),
        )
        self.assertEqual(response.status_code, 302)
        cr = CustomerRequest.objects.get(name=self.name)
        self.assertEqual(cr.status, CustomerRequest.Status.DISPATCHER_REVIEW)
        self.assertEqual(cr.target_date, self.day)
        self.assertEqual(cr.created_by_id, self.zadavatel.pk)

    def test_post_without_waste_type_uses_lookup_label(self):
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_post_data()
        data.pop("waste_type")
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 302)
        cr = CustomerRequest.objects.get(name=self.name)
        self.assertEqual(cr.waste_type_id, self.wt.pk)

    def test_post_without_subject_shows_validation_errors(self):
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_post_data(
            name_existing="",
            name_lookup="",
            address_value="",
        )
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Požadavek se nepodařilo uložit")
        self.assertEqual(CustomerRequest.objects.filter(name=self.name).count(), 0)

    def test_form_resolves_waste_type_lookup(self):
        form = CustomerRequestForm(
            self._base_post_data(waste_type="", waste_type_lookup=self.waste_label)
        )
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data["waste_type"].pk, self.wt.pk)

    def test_form_resolves_waste_type_by_code_only(self):
        form = CustomerRequestForm(
            self._base_post_data(waste_type="", waste_type_lookup="200301")
        )
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data["waste_type"].pk, self.wt.pk)

    def test_form_resolves_waste_type_with_ascii_dash(self):
        alt_label = self.waste_label.replace("—", "-")
        form = CustomerRequestForm(
            self._base_post_data(waste_type="", waste_type_lookup=alt_label)
        )
        self.assertTrue(form.is_valid(), msg=form.errors)
        self.assertEqual(form.cleaned_data["waste_type"].pk, self.wt.pk)

    def test_post_lookup_only_with_multiple_subject_wastes(self):
        wt2 = WasteTypeCatalog.objects.create(code="200302", value="W create 2")
        suf2 = SuffixCatalog.objects.create(value="KV2")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=NameSubjectProfile.objects.get(name=self.name),
            waste_type=self.wt,
            suffix=self.suf,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=NameSubjectProfile.objects.get(name=self.name),
            waste_type=wt2,
            suffix=suf2,
        )
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_post_data()
        data.pop("waste_type")
        data["waste_type_lookup"] = self.waste_label
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 302)
        cr = CustomerRequest.objects.get(name=self.name)
        self.assertEqual(cr.waste_type_id, self.wt.pk)

    def test_failed_post_preserves_waste_type_lookup_in_form(self):
        client = Client()
        client.force_login(self.zadavatel)
        data = self._base_post_data(address_value="")
        data.pop("waste_type")
        response = client.post(reverse("waste_docs:customer_request_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.waste_label)
        self.assertContains(response, 'id="id_waste_type_lookup"')

    def test_create_form_hides_pairs_button_without_catalog_access(self):
        from users.models import UserAccessProfile
        from users.services.access_profile import get_access_profile

        prof = get_access_profile(self.zadavatel)
        prof.nav_catalogs = UserAccessProfile.NavOverride.HIDE
        prof.save(update_fields=["nav_catalogs"])
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="customer-request-edit-subject-pairs-btn"')

    def test_create_form_shows_pairs_button_for_zadavatel(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="customer-request-edit-subject-pairs-btn"')
        self.assertContains(response, "customer-request-pairs-btn-wrap-waste")

    def test_create_form_shows_pairs_button_for_catalog_user(self):
        User = get_user_model()
        admin = User.objects.create_superuser("cr_pairs_admin", password="pw", email="a@b.cz")
        client = Client()
        client.force_login(admin)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="customer-request-edit-subject-pairs-btn"')
        self.assertContains(response, "customer-request-vehicle-kind-clear")
        self.assertContains(response, "customer-request-form-config")

    def test_client_config_includes_pairs_modal_url(self):
        cfg = customer_request_form_client_config(can_edit_name_subject_pairs=True)
        self.assertTrue(cfg["canEditNameSubjectPairs"])
        self.assertIn("__PROFILE_PK__", cfg["urls"]["nameSubjectPairsModal"])

    def test_client_config_includes_zpo_pairing(self):
        cfg = customer_request_form_client_config(can_edit_name_subject_pairs=False)
        zpo = cfg["zpoPairing"]
        self.assertIn("endpoint", zpo)
        self.assertIn("fieldMap", zpo)
        field_ids = [pair[1] for pair in zpo["fieldMap"]]
        self.assertIn("id_name_existing", field_ids)
        self.assertIn("id_waste_type", field_ids)

    def test_create_form_includes_zpo_dock_and_waste_meta(self):
        meta = waste_type_combo_metadata()
        row = meta[str(self.wt.pk)]
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="zpo-pairing-dock"')
        self.assertContains(response, "zpo_pairing_panel.js")
        self.assertContains(response, 'id="customer-request-waste-code"')
        self.assertContains(response, 'id="customer-request-waste-category"')
        self.assertContains(response, "customer-request-form-config")
        self.assertContains(response, row["code"])
        self.assertContains(response, "customer-request-waste-combo")

    def test_create_form_syncs_waste_meta_via_apply_pk(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "function syncWasteMetaFromHooks")
        self.assertContains(response, "wasteComboApi.applyPk")

    def test_create_form_config_always_present_without_catalog_access(self):
        from users.models import UserAccessProfile
        from users.services.access_profile import get_access_profile

        prof = get_access_profile(self.zadavatel)
        prof.nav_catalogs = UserAccessProfile.NavOverride.HIDE
        prof.save(update_fields=["nav_catalogs"])
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "customer-request-form-config")
        self.assertContains(response, 'id="zpo-pairing-dock"')
