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
    WasteTypeCatalog,
)
from catalogs.models.vehicle_rz import VehicleKindCatalog
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from customer_requests.models import CustomerRequest
from users.constants import ROLE_ZADAVATEL
from users.services.roles import set_user_role


class CustomerRequestFixTests(TestCase):
    databases = {"default", "addresses"}

    def setUp(self):
        User = get_user_model()
        self.zadavatel = User.objects.create_user("cr_fix_zad", password="pw")
        set_user_role(self.zadavatel, ROLE_ZADAVATEL)
        self.other = User.objects.create_user("cr_fix_other", password="pw")
        set_user_role(self.other, ROLE_ZADAVATEL)
        self.day = date(2038, 7, 1)

        self.name = NameCatalog.objects.create(value="Subjekt fix CR")
        self.name2 = NameCatalog.objects.create(value="Subjekt fix CR 2")
        self.ico = IcoCatalog.objects.create(value="88776655")
        NameSubjectProfile.objects.create(name=self.name, ico=self.ico)
        NameSubjectProfile.objects.create(name=self.name2, ico=self.ico)
        self.address = AddressCatalog.objects.create(value="Fix ulice, 1, Město")

        self.wt = WasteTypeCatalog.objects.create(code="200302", value="W fix")
        self.wt2 = WasteTypeCatalog.objects.create(code="200303", value="W fix 2")
        self.suf = SuffixCatalog.objects.create(value="KF")
        self.suf2 = SuffixCatalog.objects.create(value="KG")
        self.vk = VehicleKindCatalog.objects.create(name="Hák fix", shortcut="Hf", sort_order=0)
        self.activity = ActivityCatalog.objects.create(name="Svoz fix", visible_for_submitter=True)
        self.activity2 = ActivityCatalog.objects.create(name="Výměna fix", visible_for_submitter=True)

        meta = waste_type_combo_metadata()
        self.waste_label = meta[str(self.wt.pk)]["label"]
        self.waste_label2 = meta[str(self.wt2.pk)]["label"]

        self.cr = CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.RETURNED_FOR_FIX,
            dispatcher_note="Doplňte koncovku a druh vozidla.",
        )

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

    def test_fix_edit_get_for_returned_request(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Oprava požadavku")
        self.assertContains(response, self.name.value)
        self.assertContains(response, "Doplňte koncovku")

    def test_fix_edit_denied_for_other_submitter(self):
        client = Client()
        client.force_login(self.other)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_fix_save_changes_fields(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        data = self._base_post_data(
            activity=str(self.activity2.pk),
            waste_type=str(self.wt2.pk),
            waste_type_lookup=self.waste_label2,
            suffix=str(self.suf2.pk),
            name_existing=str(self.name2.pk),
            name_lookup=self.name2.value,
            action="save",
        )
        response = client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.activity_id, self.activity2.pk)
        self.assertEqual(self.cr.waste_type_id, self.wt2.pk)
        self.assertEqual(self.cr.suffix_id, self.suf2.pk)
        self.assertEqual(self.cr.name_id, self.name2.pk)
        self.assertEqual(self.cr.status, CustomerRequest.Status.RETURNED_FOR_FIX)

    def test_fix_resubmit_moves_to_dispatcher_review(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        data = self._base_post_data(action="resubmit")
        response = client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.DISPATCHER_REVIEW)

    def test_fix_delete_removes_request(self):
        pk = self.cr.pk
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_delete", args=[pk])
        response = client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CustomerRequest.objects.filter(pk=pk).exists())

    def test_fix_delete_parent_with_follow_up_child_shows_error(self):
        parent_pk = self.cr.pk
        CustomerRequest.objects.create(
            created_by=self.zadavatel,
            name=self.name,
            activity=self.activity,
            vehicle_kind=self.vk,
            waste_type=self.wt,
            suffix=self.suf,
            address=self.address,
            target_date=self.day,
            status=CustomerRequest.Status.DISPATCHER_REVIEW,
            follow_up_parent_request=self.cr,
        )
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_delete", args=[parent_pk])
        response = client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CustomerRequest.objects.filter(pk=parent_pk).exists())
        self.assertContains(response, "Požadavek nelze smazat, protože má navazující požadavek.")

    def test_detail_shows_fix_button_and_dispatcher_note(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_detail", args=[self.cr.pk])
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opravit požadavek")
        self.assertContains(response, "Doplňte koncovku")

    def test_list_shows_fix_link(self):
        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        )
        self.assertContains(response, "Opravit")

    def test_fix_form_shows_invoice_rejection_note(self):
        self.cr.status = CustomerRequest.Status.INVOICE_REJECTED
        self.cr.dispatcher_note = ""
        self.cr.invoice_note = "Chybí podklady k záloze."
        self.cr.save(update_fields=["status", "dispatcher_note", "invoice_note"])

        client = Client()
        client.force_login(self.zadavatel)
        response = client.get(reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chybí podklady k záloze")
        self.assertContains(response, "Důvod zamítnutí zálohy")

    def test_fix_cancel_requires_reason(self):
        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.post(url, {"action": "cancel"})
        self.assertEqual(response.status_code, 200)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.RETURNED_FOR_FIX)
        self.assertContains(response, "Zadejte důvod zrušení")

    def test_fix_cancel_with_reason_sets_cancelled(self):
        from customer_requests.models import CustomerRequestAuditLog

        client = Client()
        client.force_login(self.zadavatel)
        url = reverse("waste_docs:customer_request_form_edit", args=[self.cr.pk])
        response = client.post(url, {"action": "cancel", "cancel_reason": "Zákazník stornoval."})
        self.assertEqual(response.status_code, 302)
        self.cr.refresh_from_db()
        self.assertEqual(self.cr.status, CustomerRequest.Status.CANCELLED)
        log = CustomerRequestAuditLog.objects.filter(request=self.cr, action="cancel").latest("id")
        self.assertEqual(log.note, "Zákazník stornoval.")
