from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase
from django.urls import reverse

from catalogs.models import (
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    WasteTypeCatalog,
)
from pio.models import PioRevision
from pio.services.global_search import search_pio_items


class PioGlobalSearchServiceTests(TestCase):
    def setUp(self):
        self.name = NameCatalog.objects.create(value="PIO search subjekt")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            ico=IcoCatalog.objects.create(value="12345678"),
            company_name="PIO Search s.r.o.",
        )
        self.waste = WasteTypeCatalog.objects.create(code="17 05 04", value="Odpad hledání")
        self.suffix = SuffixCatalog.objects.create(value="Koncovka hledání")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.waste,
            suffix=self.suffix,
        )

    def test_active_pio_appears_in_search(self):
        self.pair.pio_document.save("active_pio.pdf", ContentFile(b"%PDF-1.4"), save=True)
        items = search_pio_items()
        kinds = {item.kind for item in items}
        self.assertIn("active", kinds)
        active = [i for i in items if i.kind == "active" and i.pair.pk == self.pair.pk]
        self.assertEqual(len(active), 1)

    def test_revision_appears_in_search(self):
        rev = PioRevision(pair=self.pair, note="Test revize")
        rev.file.save("rev_pio.pdf", ContentFile(b"%PDF-1.4"), save=True)
        items = search_pio_items()
        revision = [i for i in items if i.kind == "revision" and i.revision and i.revision.pk == rev.pk]
        self.assertEqual(len(revision), 1)

    def test_text_query_finds_active_by_company_name(self):
        self.pair.pio_document.save("active_pio.pdf", ContentFile(b"%PDF-1.4"), save=True)
        items = search_pio_items(q="PIO Search")
        self.assertTrue(any(i.kind == "active" and i.pair.pk == self.pair.pk for i in items))

    def test_text_query_finds_revision_by_note(self):
        rev = PioRevision(pair=self.pair, note="Unikatni poznamka revize")
        rev.file.save("rev_pio.pdf", ContentFile(b"%PDF-1.4"), save=True)
        items = search_pio_items(q="Unikatni poznamka")
        self.assertTrue(any(i.kind == "revision" and i.revision and i.revision.pk == rev.pk for i in items))

    def test_empty_when_no_pio(self):
        items = search_pio_items(q="PIO Search")
        self.assertEqual(items, [])


class PioGlobalSearchViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="pio_search_admin", password="pw", email="a@b.c")
        self.user = User.objects.create_user(username="pio_search_user", password="pw")
        self.client = Client()
        self.url = reverse("catalogs:name_pio_search")

        name = NameCatalog.objects.create(value="PIO view subjekt")
        self.subject = NameSubjectProfile.objects.create(
            name=name,
            company_name="PIO View firma",
        )
        waste = WasteTypeCatalog.objects.create(code="20 01 01", value="View odpad")
        suffix = SuffixCatalog.objects.create(value="View koncovka")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=waste,
            suffix=suffix,
        )
        self.pair.pio_document.save("view_active.pdf", ContentFile(b"%PDF-1.4"), save=True)

    def test_superuser_sees_active_pio(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {"q": "PIO View"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aktivní")
        self.assertContains(response, "PIO View firma")

    def test_non_superuser_is_denied(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertIn(response.status_code, (302, 403, 404))
