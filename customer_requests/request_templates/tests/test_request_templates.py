from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.catalog_nav_registry import SLUG_CUSTOMER_REQUEST_TEMPLATES
from catalogs.models import AddressCatalog, NameCatalog, WasteTypeCatalog
from customer_requests.request_templates.models import CustomerRequestTemplate
from customer_requests.request_templates.services.create_from_payload import (
    create_customer_request_template_from_payload,
)
from customer_requests.request_templates.services.visibility import (
    customer_request_templates_visible_queryset,
)
from users.constants import ROLE_ADMIN, ROLE_ZADAVATEL
from users.models import UserAccessProfile
from users.services.roles import set_user_role


class CustomerRequestTemplateVisibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="tpl_owner", password="x")
        self.other = user_model.objects.create_user(username="tpl_other", password="x")
        self.admin = user_model.objects.create_user(username="tpl_admin", password="x")
        set_user_role(self.admin, ROLE_ADMIN)
        self.name = NameCatalog.objects.create(value="Subjekt šablony")
        self.waste = WasteTypeCatalog.objects.create(code="200101", value="Test odpad")
        self.address = AddressCatalog.objects.create(value="Ulice, 1, Město")
        self.template = CustomerRequestTemplate.objects.create(
            title="Moje šablona",
            created_by=self.owner,
            name=self.name,
            waste_type=self.waste,
            address=self.address,
        )

    def test_user_sees_only_own_templates(self):
        qs = customer_request_templates_visible_queryset(self.owner)
        self.assertEqual(list(qs.values_list("pk", flat=True)), [self.template.pk])
        self.assertEqual(customer_request_templates_visible_queryset(self.other).count(), 0)

    def test_admin_sees_all_templates(self):
        self.assertEqual(
            customer_request_templates_visible_queryset(self.admin).count(),
            1,
        )

    def test_create_from_payload(self):
        tpl = create_customer_request_template_from_payload(
            user=self.owner,
            payload={
                "title": "Nová",
                "name_id": self.name.pk,
                "waste_type_id": self.waste.pk,
                "address_value": "Jiná, 2, Město",
            },
        )
        self.assertEqual(tpl.title, "Nová")
        self.assertEqual(tpl.created_by_id, self.owner.pk)
        self.assertEqual(tpl.address.value, "Jiná, 2, Město")
        self.assertFalse(tpl.is_recurring)

    def test_create_from_payload_saves_weekdays_without_dates(self):
        tpl = create_customer_request_template_from_payload(
            user=self.owner,
            payload={
                "title": "Pravidelná",
                "name_id": self.name.pk,
                "waste_type_id": self.waste.pk,
                "address_value": "Pravidelná, 1, Město",
                "is_recurring": True,
                "recurrence_weekdays": "0,3,6",
                "target_date": "2026-08-10",
                "recurrence_until": "2026-12-31",
            },
        )
        self.assertTrue(tpl.is_recurring)
        self.assertEqual(tpl.recurrence_weekdays, "0,3,6")
        from customer_requests.request_templates.services.serialization import (
            customer_request_template_to_json,
        )

        data = customer_request_template_to_json(tpl)
        self.assertTrue(data["is_recurring"])
        self.assertEqual(data["recurrence_weekdays"], "0,3,6")
        self.assertNotIn("target_date", data)
        self.assertNotIn("recurrence_until", data)


class CustomerRequestTemplateApiTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="cr_tpl_user", password="x")
        set_user_role(self.user, ROLE_ZADAVATEL)
        profile, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        profile.catalog_item_nav = {SLUG_CUSTOMER_REQUEST_TEMPLATES: UserAccessProfile.NavOverride.SHOW}
        profile.save(update_fields=["catalog_item_nav"])
        self.client = Client()
        self.client.force_login(self.user)
        self.name = NameCatalog.objects.create(value="API subjekt")
        self.waste = WasteTypeCatalog.objects.create(code="200102", value="API odpad")
        self.address = AddressCatalog.objects.create(value="API, 1, Město")
        self.template = CustomerRequestTemplate.objects.create(
            title="API šablona",
            created_by=self.user,
            name=self.name,
            waste_type=self.waste,
            address=self.address,
        )

    def test_api_list_returns_own_template(self):
        response = self.client.get(reverse("customer_request_templates:api_list"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["title"], "API šablona")

    def test_api_save_creates_template(self):
        response = self.client.post(
            reverse("customer_request_templates:api_save"),
            data=(
                '{"title":"Uložená","name_id":%d,"waste_type_id":%d,'
                '"address_value":"Save, 3, Město","is_recurring":true,'
                '"recurrence_weekdays":"0,1,2,3,4,5,6"}'
            )
            % (self.name.pk, self.waste.pk),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        tpl = CustomerRequestTemplate.objects.get(title="Uložená")
        self.assertTrue(tpl.is_recurring)
        self.assertEqual(tpl.recurrence_weekdays, "0,1,2,3,4,5,6")
        self.assertEqual(payload["data"]["recurrence_weekdays"], "0,1,2,3,4,5,6")
        self.assertNotIn("target_date", payload["data"])
        self.assertNotIn("recurrence_until", payload["data"])
