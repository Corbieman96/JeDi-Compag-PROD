"""ZPO panel při zakládání průvodky — jen z řádků stejného zdroje jako odpad na /new/."""

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from catalogs.models import (
    ActivityCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
    ZpoDocument,
)


class ZpoPairingDraftYardFilterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("zpo_draft", password="pw")
        self.client.force_login(self.user)

        self.name = NameCatalog.objects.create(value="Dvůr ZPO draft")
        self.subject = NameSubjectProfile.objects.create(name=self.name, company_name="Yard ZPO")
        self.subject.yard_settings.is_collection_yard = True
        self.subject.yard_settings.save()

        self.wt = WasteTypeCatalog.objects.create(code="200307", value="O-zpo")
        self.suf_svoz = SuffixCatalog.objects.create(value="K-svoz-zpo")
        self.suf_new = SuffixCatalog.objects.create(value="K-new-zpo")
        self.vk = VehicleKindCatalog.objects.create(name="Voz ZPO", shortcut="Z")
        self.activity = ActivityCatalog.objects.create(name="A ZPO")
        self.zpo_doc = ZpoDocument.objects.create(label="ZPO yard draft")
        self.zpo_doc.file.save("zpo/yard_draft.pdf", ContentFile(b"%PDF"), save=True)

        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_svoz,
            yard_svoz_enabled=True,
            yard_pruvodka_enabled=False,
            yard_vehicle_kind=self.vk,
            yard_svoz_activity=self.activity,
            zpo=self.zpo_doc,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.wt,
            suffix=self.suf_new,
            yard_svoz_enabled=False,
            yard_pruvodka_enabled=True,
            yard_vehicle_kind=self.vk,
            yard_pruvodka_activity=self.activity,
        )

    def test_zpo_from_svoz_only_row_not_used_on_new_date(self):
        url = reverse("waste_docs:zpo_pairing_draft")
        response = self.client.get(
            url,
            {
                "name_id": self.name.pk,
                "waste_type_id": self.wt.pk,
                "suffix_id": self.suf_svoz.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["has_zpo"])

    def test_zpo_without_suffix_uses_new_date_row_only(self):
        pair_new = NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=self.subject, suffix=self.suf_new
        ).first()
        pair_new.zpo = self.zpo_doc
        pair_new.save(update_fields=["zpo"])

        url = reverse("waste_docs:zpo_pairing_draft")
        response = self.client.get(
            url,
            {
                "name_id": self.name.pk,
                "waste_type_id": self.wt.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["has_zpo"])
