from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalogs.catalog_definitions import CATALOGS, HIDDEN_CATALOG_SLUGS
from catalogs.catalog_nav_registry import (
    SLUG_OFFLINE_ADDRESSES,
    SLUG_PASPORT_STREDISKO,
    SLUG_RIDE_TEMPLATES,
    catalog_index_rows,
    iter_index_slugs_ordered,
)
from catalogs.models import (
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    NameSubjectWasteSuffixPair,
    SuffixCatalog,
    SuffixSiteProfile,
    WasteTypeCatalog,
)
from catalogs.services.suffix_catalog_scope import suffix_catalog_queryset_for_subject_pair_select
from catalogs.services.suffix_merge import merge_suffix_catalog_rows
from catalogs.services.fulfillment_address import normalize_fulfillment_address
from catalogs.services.waste_type_labels import waste_type_combo_metadata
from catalogs.services.waste_type_lookup import (
    normalize_waste_combo_text,
    resolve_waste_type_from_combo_text,
)


class WasteTypeLookupTests(TestCase):
    def setUp(self):
        self.wt = WasteTypeCatalog.objects.create(code="200140", value="Kovy")
        self.meta = waste_type_combo_metadata()
        self.label = self.meta[str(self.wt.pk)]["label"]

    def test_exact_label(self):
        found = resolve_waste_type_from_combo_text(self.label)
        self.assertEqual(found.pk, self.wt.pk)

    def test_ascii_dash_label(self):
        alt = self.label.replace("—", "-")
        found = resolve_waste_type_from_combo_text(alt)
        self.assertEqual(found.pk, self.wt.pk)

    def test_code_only(self):
        found = resolve_waste_type_from_combo_text("200140")
        self.assertEqual(found.pk, self.wt.pk)

    def test_code_with_spaces(self):
        found = resolve_waste_type_from_combo_text("20 01 40")
        self.assertEqual(found.pk, self.wt.pk)

    def test_normalize_dashes(self):
        self.assertEqual(
            normalize_waste_combo_text("20 01 40 - Kovy"),
            normalize_waste_combo_text("20 01 40 — Kovy"),
        )

    def test_allowed_ids_filter(self):
        other = WasteTypeCatalog.objects.create(code="200141", value="Jiný")
        found = resolve_waste_type_from_combo_text(
            self.label,
            allowed_ids={other.pk},
        )
        self.assertIsNone(found)

    def test_unknown_text(self):
        self.assertIsNone(resolve_waste_type_from_combo_text("neexistující odpad xyz"))


class CatalogDefinitionsTests(SimpleTestCase):
    def test_catalogs_registry_non_empty(self):
        self.assertIsInstance(CATALOGS, dict)
        self.assertGreater(len(CATALOGS), 0)


class CatalogNavRegistryTests(SimpleTestCase):
    def test_catalog_index_ordered_slugs_unique(self):
        ordered = iter_index_slugs_ordered()
        self.assertEqual(len(ordered), len(set(ordered)))
        self.assertEqual(ordered[:2], ("name", "suffix"))
        self.assertIn(SLUG_OFFLINE_ADDRESSES, ordered)
        self.assertIn(SLUG_RIDE_TEMPLATES, ordered)
        self.assertIn(SLUG_PASPORT_STREDISKO, ordered)

    def test_catalog_index_rows_includes_every_visible_catalog_slug(self):
        slugs_from_rows = {slug for slug, _ in catalog_index_rows()}
        for slug in CATALOGS:
            if slug not in HIDDEN_CATALOG_SLUGS:
                self.assertIn(slug, slugs_from_rows)


class SuffixCatalogScopeTests(TestCase):
    def test_pair_select_includes_full_catalog_one_per_normalized_value(self):
        """Nabídka pokrývá celý číselník; u stejného textu po normalizaci jen jeden řádek."""
        SuffixCatalog.objects.create(value="jen osiřelý řádek")
        SuffixCatalog.objects.create(value="druhá koncovka")
        qs = suffix_catalog_queryset_for_subject_pair_select(must_include_ids=())
        self.assertEqual(qs.count(), 2)

    def test_pair_select_must_include_shows_orphan_for_current_row(self):
        """Aktuální výběr řádku zůstane ve výběru i u osiřelého PK (např. před uložením)."""
        orphan = SuffixCatalog.objects.create(value="jen v tomto řádku")
        qs = suffix_catalog_queryset_for_subject_pair_select(must_include_ids=(orphan.pk,))
        self.assertIn(orphan.pk, set(qs.values_list("pk", flat=True)))

    def test_pair_select_collapses_normalized_duplicate_values_when_both_allowed(self):
        """Dvě hodnoty se stejným normalizovaným textem → jedna položka, pokud jsou obě v povolené množině."""
        a = SuffixCatalog.objects.create(value="  dup  ")
        b = SuffixCatalog.objects.create(value="dup")
        qs = suffix_catalog_queryset_for_subject_pair_select(must_include_ids=(a.pk, b.pk))
        self.assertEqual(qs.count(), 1)


class SuffixMergeTests(TestCase):
    def test_merge_deletes_source_suffix_row(self):
        src = SuffixCatalog.objects.create(value="typo variant")
        tgt = SuffixCatalog.objects.create(value="correct variant")
        merge_suffix_catalog_rows(source_pk=src.pk, target_pk=tgt.pk)
        self.assertFalse(SuffixCatalog.objects.filter(pk=src.pk).exists())
        self.assertTrue(SuffixCatalog.objects.filter(pk=tgt.pk).exists())

    def test_merge_two_suffix_site_profiles_keeps_one_on_target(self):
        src = SuffixCatalog.objects.create(value="merge src site")
        tgt = SuffixCatalog.objects.create(value="merge tgt site")
        SuffixSiteProfile.objects.create(suffix=src, name="Profil zdroj")
        SuffixSiteProfile.objects.create(suffix=tgt, name="Profil cíl")
        stats = merge_suffix_catalog_rows(source_pk=src.pk, target_pk=tgt.pk)
        self.assertEqual(stats.get("site_profiles_merged"), 1)
        self.assertFalse(SuffixCatalog.objects.filter(pk=src.pk).exists())
        self.assertEqual(SuffixSiteProfile.objects.count(), 1)
        self.assertEqual(SuffixSiteProfile.objects.get().name, "Profil cíl")


class ContainerPassportVokMappingTests(SimpleTestCase):
    def test_resolve_vok_and_atego(self):
        from catalogs.services.container_passport_vok_mapping import resolve_vehicle_kind_shortcut

        self.assertEqual(resolve_vehicle_kind_shortcut("100_VOK"), "100_VOK")
        self.assertEqual(resolve_vehicle_kind_shortcut("100 vok"), "100_VOK")
        self.assertEqual(resolve_vehicle_kind_shortcut("Řetěz VOK"), "100_VOK")
        self.assertEqual(resolve_vehicle_kind_shortcut("Hák"), "300_ATEGO")
        self.assertEqual(resolve_vehicle_kind_shortcut("Atego"), "300_ATEGO")
        self.assertEqual(resolve_vehicle_kind_shortcut("300_ATEGO"), "300_ATEGO")

    def test_resolve_rejects_plain_word_typ_cell(self):
        from catalogs.services.container_passport_vok_mapping import resolve_vehicle_kind_shortcut

        with self.assertRaises(ValueError):
            resolve_vehicle_kind_shortcut("VANA")

    @override_settings(VOK_IMPORT_SHEET_KIND_MAP={"100_VOK": "H"})
    def test_resolve_import_uses_settings_map(self):
        from catalogs.services.container_passport_vok_mapping import resolve_vok_import_to_catalog_shortcut

        cat = frozenset({"H"})
        self.assertEqual(resolve_vok_import_to_catalog_shortcut("100_VOK", "VANA", catalog_shortcuts=cat), "H")

    def test_resolve_import_exact_sheet_shortcut(self):
        from catalogs.services.container_passport_vok_mapping import resolve_vok_import_to_catalog_shortcut

        cat = frozenset({"100_VOK", "300_ATEGO"})
        self.assertEqual(resolve_vok_import_to_catalog_shortcut("100_VOK", "", catalog_shortcuts=cat), "100_VOK")
        self.assertEqual(
            resolve_vok_import_to_catalog_shortcut("300_ATEGO_(AVIA)", "", catalog_shortcuts=cat),
            "300_ATEGO",
        )

    def test_sheet_alias_maps_before_exact_sheet_name(self):
        """Mapa list → zkratka má přednost před záznamem v číselníku se stejným názvem jako list."""
        from catalogs.services.container_passport_vok_mapping import resolve_vok_import_to_catalog_shortcut

        cat = frozenset({"300_ATEGO", "H"})
        self.assertEqual(resolve_vok_import_to_catalog_shortcut("300_ATEGO_(AVIA)", "", catalog_shortcuts=cat), "H")

    def test_parse_size_and_requirement(self):
        from decimal import Decimal

        from catalogs.services.container_passport_vok_mapping import (
            parse_container_size_ft,
            parse_volume_m3,
            vehicle_requirement_for_size_ft,
            vehicle_requirement_for_volume_m3,
        )

        self.assertEqual(parse_container_size_ft("40'"), 40)
        self.assertEqual(parse_container_size_ft(20), 20)
        self.assertIsNone(parse_container_size_ft(""))
        self.assertEqual(vehicle_requirement_for_size_ft(40), "3H")
        self.assertEqual(vehicle_requirement_for_size_ft(20), "")
        self.assertEqual(parse_volume_m3("7,00"), Decimal("7"))
        self.assertEqual(parse_volume_m3("40"), Decimal("40"))
        self.assertEqual(vehicle_requirement_for_volume_m3(Decimal("40")), "3H")
        self.assertEqual(vehicle_requirement_for_volume_m3(Decimal("7")), "")


class NameSubjectPairsModalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="pairs_modal", password="x")
        from users.models import UserAccessProfile

        prof, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        prof.nav_catalogs = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_catalogs"])
        self.client = Client()
        self.client.force_login(self.user)

        self.name = NameCatalog.objects.create(value="Test FP")
        self.ico = IcoCatalog.objects.create(value="12345678")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            ico=self.ico,
            company_name="Test FP s.r.o.",
        )
        self.waste = WasteTypeCatalog.objects.create(code="20 03 01", value="Odpad A")
        self.suffix = SuffixCatalog.objects.create(value="Koncovka A")

    def test_get_modal_ok(self):
        url = reverse("catalogs:name_pairs_modal", args=[self.subject.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Povolené odpady a koncovky")

    def test_post_add_pair_returns_snapshot(self):
        url = reverse("catalogs:name_pairs_modal", args=[self.subject.pk])
        prefix = "waste_suffix_pairs"
        data = {
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "0",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "50",
            f"{prefix}-0-waste_type": str(self.waste.pk),
            f"{prefix}-0-suffix": str(self.suffix.pk),
            f"{prefix}-0-sort_order": "0",
        }
        post = self.client.post(
            url,
            data,
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(post.status_code, 200, post.json().get("error", post.content))
        payload = post.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["subject"]["subject_profile_id"], self.subject.pk)
        self.assertTrue(
            NameSubjectWasteSuffixPair.objects.filter(
                subject_profile=self.subject,
                waste_type=self.waste,
                suffix=self.suffix,
            ).exists()
        )
        self.subject.refresh_from_db()
        self.assertIn(self.waste, self.subject.allowed_waste_types.all())


class ZpoListSearchTests(TestCase):
    def test_search_terms_compact_and_spaced(self):
        from catalogs.services.zpo_list_search import zpo_search_terms

        compact_terms = zpo_search_terms("190904")
        self.assertIn("190904", compact_terms)
        self.assertIn("19 09 04", compact_terms)

        spaced_terms = zpo_search_terms("19 09 04")
        self.assertIn("190904", spaced_terms)
        self.assertIn("19 09 04", spaced_terms)

    def test_filter_finds_label_with_either_code_format(self):
        from catalogs.models import ZpoDocument
        from catalogs.services.zpo_list_search import filter_zpo_documents_for_query

        ZpoDocument.objects.create(label="ZPO 19 09 04 test")
        qs = ZpoDocument.objects.all()
        self.assertEqual(filter_zpo_documents_for_query(qs, "190904").count(), 1)
        self.assertEqual(filter_zpo_documents_for_query(qs, "19 09 04").count(), 1)


class NameSubjectIcoValidationTests(TestCase):
    def test_eight_digit_name_without_ico_field_errors(self):
        from catalogs.forms import NameSubjectProfileForm

        form = NameSubjectProfileForm(
            data={
                "name_value": "10700854",
                "ico_value": "",
                "facility_address_value": "",
                "fulfillment_address_value": "Ulice 1, 1, Praha",
                "is_municipality": False,
                "nitropodnikovy_subjekt": False,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name_value", form.errors)
        self.assertIn("IČO patří", form.errors["name_value"][0])


class FulfillmentAddressTests(SimpleTestCase):
    def test_normalize_street_number_city_to_strict_format(self):
        from catalogs.services.fulfillment_address import (
            is_valid_fulfillment_address_strict,
            normalize_fulfillment_address,
        )

        normalized = normalize_fulfillment_address("Obecní úřad 45 Kolomuty")
        self.assertEqual(normalized, "Obecní úřad, 45, Kolomuty")
        self.assertTrue(is_valid_fulfillment_address_strict(normalized))

    def test_alphanumeric_house_number_is_valid(self):
        """Číslo popisné s písmenem (např. areálové M2) je platné."""
        from catalogs.services.fulfillment_address import (
            is_valid_fulfillment_address_strict,
            normalize_fulfillment_address,
        )

        for addr in (
            "třída Václava Klementa, M2, Mladá Boleslav",
            "Nádražní, 123a, Praha",
            "Hlavní, 123/45b, Brno",
        ):
            normalized = normalize_fulfillment_address(addr)
            self.assertTrue(
                is_valid_fulfillment_address_strict(normalized),
                f"Adresa měla být platná: {addr!r} -> {normalized!r}",
            )


class ReverseGeocodeTests(TestCase):
    def test_reverse_geocode_prefers_osm_and_returns_pin_coords(self):
        from unittest.mock import patch

        from address_data.services.offline_lookup import reverse_geocode

        with (
            patch(
                "address_data.services.offline_lookup.ruian_reverse_geocode",
                return_value=None,
            ),
            patch(
                "address_data.services.offline_lookup.reverse_geocode_czech_with_payload",
                return_value=(
                    {
                        "city": "Kolomuty",
                        "street": "Obecní úřad",
                        "house_number": "1",
                        "postal_code": "29412",
                        "label": "Obecní úřad, 1, Kolomuty",
                        "lat": 50.123,
                        "lng": 15.456,
                    },
                    None,
                ),
            ),
            patch("address_data.services.offline_lookup.upsert_offline_rows"),
            patch("address_data.services.offline_lookup._reverse_geocode_offline", return_value=None),
        ):
            result = reverse_geocode(lat=50.9991234, lng=15.8887654)
        self.assertIsNotNone(result)
        self.assertEqual(result["lat"], 50.9991234)
        self.assertEqual(result["lng"], 15.8887654)
        self.assertEqual(result["label"], "Obecní úřad, 1, Kolomuty")

    def test_address_reverse_geocode_view_returns_normalized_label(self):
        from unittest.mock import patch

        user = get_user_model().objects.create_superuser(
            username="reverse_geocode_view",
            email="reverse@test.local",
            password="test-pass",
        )
        self.client.force_login(user)
        with patch(
            "catalogs.views.name_subject.reverse_geocode",
            return_value={
                "lat": 50.417400093481305,
                "lng": 14.91126251214155,
                "label": "Boženy Němcové, 378/2, Mladá Boleslav",
            },
        ):
            response = self.client.get(
                reverse("catalogs:name_address_reverse_geocode"),
                {"lat": "50.417400093481305", "lng": "14.91126251214155"},
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            payload["data"]["label"],
            normalize_fulfillment_address("Boženy Němcové, 378/2, Mladá Boleslav"),
        )


class NameSubjectFulfillmentSaveTests(TestCase):
    def test_form_save_persists_fulfillment_address_and_coords(self):
        from decimal import Decimal

        from catalogs.forms import NameSubjectProfileForm

        name = NameCatalog.objects.create(value="Test subjekt plnění")
        profile = NameSubjectProfile.objects.create(name=name, company_name="Test subjekt plnění")
        form = NameSubjectProfileForm(
            data={
                "name_value": "Test subjekt plnění",
                "ico_value": "",
                "facility_address_value": "",
                "fulfillment_address_value": "Kolomuty, 1, Kolomuty",
                "fulfillment_latitude": "50.1234567",
                "fulfillment_longitude": "15.7654321",
                "fulfillment_orp": "2115",
                "fulfillment_iczuj": "570974",
                "is_municipality": False,
                "nitropodnikovy_subjekt": False,
            },
            instance=profile,
        )
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertEqual(saved.fulfillment_address.value, "Kolomuty, 1, Kolomuty")
        self.assertEqual(saved.fulfillment_latitude, Decimal("50.1234567"))
        self.assertEqual(saved.fulfillment_longitude, Decimal("15.7654321"))
        self.assertEqual(saved.fulfillment_orp, "2115")
        self.assertEqual(saved.fulfillment_iczuj, "570974")


class NameSubjectPioClearTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.core.files.base import ContentFile

        from catalogs.services.name_subject_pairs_save import save_name_subject_waste_suffix_pairs
        from pio.models import PioRevision
        from users.models import UserAccessProfile

        self._save_pairs = save_name_subject_waste_suffix_pairs
        self._PioRevision = PioRevision
        self._ContentFile = ContentFile

        User = get_user_model()
        self.user = User.objects.create_user(username="pio_clear_user", password="x")
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        prof.nav_catalogs = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_catalogs"])
        self.admin = User.objects.create_superuser(username="pio_admin", password="x", email="a@b.cz")
        self.client = Client()

        self.name = NameCatalog.objects.create(value="PIO clear FP")
        self.ico = IcoCatalog.objects.create(value="99887766")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            ico=self.ico,
            company_name="PIO clear s.r.o.",
        )
        self.waste = WasteTypeCatalog.objects.create(code="20 03 99", value="Odpad PIO")
        self.suffix = SuffixCatalog.objects.create(value="Koncovka PIO")
        self.pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=self.waste,
            suffix=self.suffix,
        )

    def _set_active_pio(self):
        self.pair.pio_document.save("legacy_pio.pdf", self._ContentFile(b"%PDF-1.4"), save=True)
        self.pair.refresh_from_db()

    def _pair_formset_post(self, **extra):
        from django.http import QueryDict

        prefix = "waste_suffix_pairs"
        data = QueryDict(mutable=True)
        data.update(
            {
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "1",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "50",
                f"{prefix}-0-id": str(self.pair.pk),
                f"{prefix}-0-waste_type": str(self.waste.pk),
                f"{prefix}-0-suffix": str(self.suffix.pk),
                f"{prefix}-0-sort_order": "0",
            }
        )
        data.update(extra)
        return data

    def test_clear_pio_document_via_formset_archives_and_keeps_pair(self):
        self._set_active_pio()
        post = self._pair_formset_post(**{"waste_suffix_pairs-0-pio_document-clear": "on"})
        result = self._save_pairs(self.subject, self.user, post, None)
        self.assertTrue(result.ok, result.error_text)
        self.pair.refresh_from_db()
        self.assertFalse(self.pair.pio_document)
        self.assertEqual(self._PioRevision.objects.filter(pair=self.pair).count(), 1)
        self.assertTrue(NameSubjectWasteSuffixPair.objects.filter(pk=self.pair.pk).exists())

    def test_archive_active_pio_from_archive_page(self):
        self._set_active_pio()
        self.client.force_login(self.user)
        url = reverse("catalogs:name_pair_pio_archive_active", args=[self.subject.pk, self.pair.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.pair.refresh_from_db()
        self.assertFalse(self.pair.pio_document)
        self.assertEqual(self._PioRevision.objects.filter(pair=self.pair).count(), 1)

    def test_effective_pio_uses_active_field_only(self):
        from pio.services import effective_pio_file

        self._set_active_pio()
        self._PioRevision.objects.create(
            pair=self.pair,
            file=self._ContentFile(b"%PDF-rev", name="rev.pdf"),
            created_by=self.user,
        )
        self.assertEqual(effective_pio_file(self.pair), self.pair.pio_document)

        post = self._pair_formset_post(**{"waste_suffix_pairs-0-pio_document-clear": "on"})
        self._save_pairs(self.subject, self.user, post, None)
        self.pair.refresh_from_db()
        self.assertIsNone(effective_pio_file(self.pair))
        self.assertEqual(self._PioRevision.objects.filter(pair=self.pair).count(), 2)

    def test_edit_page_shows_pio_archive_checkbox(self):
        self.client.force_login(self.user)
        url = reverse("catalogs:name_edit", args=[self.subject.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Přesunout PIO do archivu")


class NameSubjectPioProfileResetTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from catalogs.models import SubjectPioProfile
        from users.models import UserAccessProfile

        self._SubjectPioProfile = SubjectPioProfile
        User = get_user_model()
        self.user = User.objects.create_user(username="pio_reset_user", password="x")
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        prof.nav_catalogs = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_catalogs"])
        self.client = Client()
        self.client.force_login(self.user)

        self.name = NameCatalog.objects.create(value="PIO reset FP")
        self.subject = NameSubjectProfile.objects.create(
            name=self.name,
            company_name="PIO reset s.r.o.",
        )
        self.waste = WasteTypeCatalog.objects.create(code="20 02 01", value="Bio odpad")
        self.suffix = SuffixCatalog.objects.create(value="Kompostárna test")
        pio = self._SubjectPioProfile.objects.get(subject=self.subject)
        pio.pio_officer_name = "Holub"
        pio.pio_officer_phone = "728340215"
        pio.pio_officer_email = "holub@example.com"
        pio.pio_waste_type = self.waste
        pio.pio_suffix = self.suffix
        pio.save()

    def test_edit_form_does_not_prefill_pio_profile_fields(self):
        url = reverse("catalogs:name_edit", args=[self.subject.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn('value="Holub"', content)
        self.assertNotIn("holub@example.com", content)

    def test_save_clears_pio_profile_in_database(self):
        from catalogs.forms import NameSubjectProfileForm

        form = NameSubjectProfileForm(
            data={
                "name_value": self.name.value,
                "ico_value": "",
                "facility_address_value": "Za Drahou 165 1 Krnov 79401",
                "fulfillment_address_value": "",
                "pio_officer_name": "Dočasný",
                "pio_officer_phone": "777111222",
                "pio_officer_email": "docasny@example.com",
                "is_municipality": False,
                "nitropodnikovy_subjekt": False,
            },
            instance=self.subject,
            actor_user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        pio = self._SubjectPioProfile.objects.get(subject=self.subject)
        self.assertEqual(pio.pio_officer_name, "")
        self.assertEqual(pio.pio_officer_email, "")
        self.assertIsNone(pio.pio_waste_type_id)
        self.assertIsNone(pio.pio_suffix_id)


class PioPairSyncTests(TestCase):
    def setUp(self):
        from django.http import QueryDict

        from catalogs.models import (
            ActivityCatalog,
            VehicleKindCatalog,
            ZpoDocument,
            WasteTypeCatalog,
        )

        self.QueryDict = QueryDict
        self.activity = ActivityCatalog.objects.create(name="Činnost pro ZPO")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H")

        self.wt_src = WasteTypeCatalog.objects.create(code="20 01 01", value="Zdroj WT")
        self.wt_target = WasteTypeCatalog.objects.create(code="20 01 02", value="Cíl WT")
        self.suf_src = SuffixCatalog.objects.create(value="Zdroj SUF")
        self.suf_target = SuffixCatalog.objects.create(value="Cíl SUF")

        self.profile = NameSubjectProfile.objects.create(name=NameCatalog.objects.create(value="Subjekt PIO"))

        self.src_pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt_src,
            suffix=self.suf_src,
        )
        self.src_pair.yard_vehicle_kinds.add(self.vk_h)
        self.src_pair.yard_svoz_activity = None
        self.src_pair.yard_pruvodka_activity = None
        self.src_pair.zpo = None
        self.src_pair.suppress_system_zpo = False
        self.src_pair.save(
            update_fields=[
                "yard_svoz_activity",
                "yard_pruvodka_activity",
                "zpo",
                "suppress_system_zpo",
            ]
        )

    def _make_post(self, *, wt_id: int, suf_id: int):
        return self.QueryDict(f"pio_waste_type={wt_id}&pio_suffix={suf_id}")

    def test_creates_pair_and_copies_vehicle_kinds(self):
        from catalogs.services.pio_pair_sync import ensure_name_subject_pair_exists_from_pio_live_post

        post = self._make_post(wt_id=self.wt_target.pk, suf_id=self.suf_target.pk)
        pair = ensure_name_subject_pair_exists_from_pio_live_post(self.profile, post)

        self.assertTrue(
            NameSubjectWasteSuffixPair.objects.filter(
                subject_profile=self.profile, waste_type=self.wt_target, suffix=self.suf_target
            ).exists()
        )
        self.assertIn(self.vk_h.pk, set(pair.yard_vehicle_kinds.values_list("pk", flat=True)))

    def test_raises_when_zpo_required_and_missing_but_pair_exists(self):
        from catalogs.services.pio_pair_sync import ensure_name_subject_pair_exists_from_pio_live_post

        # Aktivita generuje ZPO (default režim), takže chybějící ZPO na novém páru musí blokovat.
        self.src_pair.yard_svoz_activity = self.activity
        self.src_pair.save(update_fields=["yard_svoz_activity"])

        post = self._make_post(wt_id=self.wt_target.pk, suf_id=self.suf_target.pk)
        try:
            ensure_name_subject_pair_exists_from_pio_live_post(self.profile, post)
            self.fail("Expected RuntimeError")
        except RuntimeError:
            pass

        # A zároveň musí záznam vzniknout (bez toho by uživatel neměl kde vybrat ZPO).
        self.assertTrue(
            NameSubjectWasteSuffixPair.objects.filter(
                subject_profile=self.profile, waste_type=self.wt_target, suffix=self.suf_target
            ).exists()
        )

    def test_existing_pair_vehicle_kinds_not_overwritten(self):
        from catalogs.services.pio_pair_sync import ensure_name_subject_pair_exists_from_pio_live_post
        from catalogs.models import VehicleKindCatalog

        other_vk = VehicleKindCatalog.objects.create(name="3H", shortcut="3H")
        existing = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.profile,
            waste_type=self.wt_target,
            suffix=self.suf_target,
        )
        existing.yard_vehicle_kinds.add(other_vk)

        post = self._make_post(wt_id=self.wt_target.pk, suf_id=self.suf_target.pk)
        ensure_name_subject_pair_exists_from_pio_live_post(self.profile, post)

        existing.refresh_from_db()
        self.assertEqual(set(existing.yard_vehicle_kinds.values_list("pk", flat=True)), {other_vk.pk})


class NameSubjectPioDraftExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="pio_admin", password="x", is_superuser=True)
        self.waste = WasteTypeCatalog.objects.create(code="200301", value="Test odpad")
        self.suffix = SuffixCatalog.objects.create(value="K")

    def test_new_form_shows_pio_generate_button_with_permission(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("catalogs:name_create"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "pio-profile-excel-btn")
        self.assertContains(resp, reverse("catalogs:name_user_pio_xlsx_draft"))

    def test_draft_download_forbidden_without_permission(self):
        from users.constants import ROLE_DISPECER
        from users.models import UserAccessProfile
        from users.services.access_profile import get_access_profile
        from users.services.roles import set_user_role

        User = get_user_model()
        user = User.objects.create_user(username="pio_disp", password="x")
        set_user_role(user, ROLE_DISPECER)
        prof = get_access_profile(user)
        prof.export_pio_profile = UserAccessProfile.NavOverride.HIDE
        prof.save()

        self.client.force_login(user)
        url = reverse("catalogs:name_user_pio_xlsx_draft")
        resp = self.client.post(
            url,
            {
                "pio_officer_name": "Jan Novák",
                "pio_officer_phone": "777123456",
                "pio_officer_email": "jan@example.cz",
                "pio_waste_type": str(self.waste.pk),
                "pio_suffix": str(self.suffix.pk),
            },
        )
        self.assertEqual(resp.status_code, 403)

    def test_draft_download_returns_xlsx_when_template_available(self):
        from pathlib import Path

        from django.conf import settings

        tpl = Path(settings.BASE_DIR) / "PIO.xlsx"
        if not tpl.is_file():
            self.skipTest("PIO.xlsx není v kořeni projektu")

        self.client.force_login(self.admin)
        url = reverse("catalogs:name_user_pio_xlsx_draft")
        resp = self.client.post(
            url,
            {
                "name_value": "Test subjekt",
                "pio_officer_name": "Jan Novák",
                "pio_officer_phone": "777123456",
                "pio_officer_email": "jan@example.cz",
                "pio_waste_type": str(self.waste.pk),
                "pio_suffix": str(self.suffix.pk),
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resp["Content-Type"],
        )
        self.assertTrue(resp.content[:2] == b"PK")


class NameSubjectPairSvozStyleTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        from users.models import UserAccessProfile

        User = get_user_model()
        self.user = User.objects.create_user("nsp_style", password="pw")
        prof, _ = UserAccessProfile.objects.get_or_create(user=self.user)
        prof.nav_catalogs = UserAccessProfile.NavOverride.SHOW
        prof.save(update_fields=["nav_catalogs"])

        self.subject = NameSubjectProfile.objects.create(
            name=NameCatalog.objects.create(value="Style subj"),
            company_name="Style s.r.o.",
        )
        wt_a = WasteTypeCatalog.objects.create(code="200401", value="Odpad A")
        wt_b = WasteTypeCatalog.objects.create(code="200402", value="Odpad B")
        suf = SuffixCatalog.objects.create(value="KN")
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt_a,
            suffix=suf,
            yard_svoz_enabled=True,
            sort_order=0,
        )
        NameSubjectWasteSuffixPair.objects.create(
            subject_profile=self.subject,
            waste_type=wt_b,
            suffix=suf,
            yard_svoz_enabled=False,
            sort_order=1,
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_edit_page_renders_svoz_matrix_card_classes(self):
        url = reverse("catalogs:name_edit", args=[self.subject.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "name-subject-pairs__card--svoz-matrix")
        self.assertContains(response, "name-subject-pairs__card--no-svoz-matrix")
        self.assertContains(response, "name-subject-pairs__legend")



from datetime import date as _date

from catalogs.models import DriverAbsence, DriverProfile
from catalogs.services.driver_absence_display import (
    absence_type_chip_class,
    build_driver_absence_display_rows,
    format_absence_date_range,
)
from catalogs.services.driver_absence_profile_summary import absence_years_for_driver


class DriverAbsenceDisplayFormatTests(SimpleTestCase):
    def test_single_day(self):
        d = _date(2026, 6, 15)
        self.assertEqual(format_absence_date_range(d, d), "15.06.2026")

    def test_same_year_range(self):
        self.assertEqual(
            format_absence_date_range(_date(2026, 3, 12), _date(2026, 3, 15)),
            "12.03.–15.03.2026",
        )

    def test_cross_year_range(self):
        self.assertEqual(
            format_absence_date_range(_date(2025, 12, 28), _date(2026, 1, 5)),
            "28.12.2025–05.01.2026",
        )

    def test_vacation_chip_class(self):
        self.assertEqual(
            absence_type_chip_class(DriverAbsence.AbsenceType.VACATION),
            "driver-absence-chip--vacation",
        )


class DriverEditAbsenceCardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user("adm_drv_abs", password="pw", is_superuser=True)
        self.driver = DriverProfile.objects.create(
            personal_number="DRV-ABS-1", last_name="Novák", first_name="Jan"
        )
        self.url = reverse("catalogs:driver_edit", kwargs={"pk": self.driver.pk})
        self.client = Client()
        self.client.force_login(self.admin)

    def test_empty_state_shows_card(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "driver-absence-card")
        self.assertContains(response, "driver-absence-empty")
        self.assertContains(response, "Žádná kalendářová nepřítomnost")
        self.assertNotContains(response, "driver-absence-toolbar")

    def test_absence_row_rendered_compact(self):
        DriverAbsence.objects.create(
            driver=self.driver,
            absence_type=DriverAbsence.AbsenceType.VACATION,
            date_from=_date(2026, 3, 12),
            date_to=_date(2026, 3, 15),
            is_partial=True,
            note="Rodinná dovolená u moře",
            created_by=self.admin,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "driver-absence-toolbar")
        self.assertContains(response, 'data-driver-absence-panel')
        self.assertContains(response, 'data-year="2026"')
        self.assertContains(response, 'data-type="vacation"')
        self.assertContains(response, "driver-absence-chip--vacation")
        self.assertContains(response, "12.03.–15.03.2026")
        self.assertContains(response, "driver-absence-partial")
        self.assertContains(response, "Rodinná dovolená u moře")
        self.assertContains(response, "data-driver-absence-total-count")

    def test_absence_years_service(self):
        DriverAbsence.objects.create(
            driver=self.driver,
            absence_type=DriverAbsence.AbsenceType.SICK,
            date_from=_date(2025, 12, 28),
            date_to=_date(2026, 1, 5),
            created_by=self.admin,
        )
        self.assertEqual(absence_years_for_driver(self.driver.pk), [2026, 2025])

    def test_build_rows_preview_truncates_long_note(self):
        absence = DriverAbsence(
            driver=self.driver,
            absence_type=DriverAbsence.AbsenceType.SICK,
            date_from=_date(2026, 1, 1),
            date_to=_date(2026, 1, 1),
            note="x" * 60,
        )
        rows = build_driver_absence_display_rows([absence])
        self.assertTrue(rows[0]["note_preview"].endswith("…"))
