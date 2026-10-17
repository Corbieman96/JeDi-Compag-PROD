"""Filtr šablon jízd podle druhu vozidla — kompatibilita H ↔ 3H."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalogs.models import (
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    VehicleKindCatalog,
    WasteTypeCatalog,
)
from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache
from waste_docs.models import RideTemplate
from waste_docs.services.ride_templates import (
    expanded_vehicle_kind_ids_for_template_filter,
    filter_ride_templates_by_vehicle_kind_ids,
    ride_templates_visible_queryset,
)


class RideTemplatesByVehicleKindFilterTests(TestCase):
    def setUp(self):
        clear_vehicle_kind_compatibility_cache()
        User = get_user_model()
        self.user = User.objects.create_user(username="tpl_filter_user", password="x")
        self.vk_h = VehicleKindCatalog.objects.create(name="Hák", shortcut="H", sort_order=1)
        self.vk_3h = VehicleKindCatalog.objects.create(
            name="Tříosý hák",
            shortcut="3H",
            sort_order=2,
            parent_kind=self.vk_h,
        )
        clear_vehicle_kind_compatibility_cache()
        self.name = NameCatalog.objects.create(value="Tpl filter nm")
        self.ico = IcoCatalog.objects.create(value="12345678")
        self.address = AddressCatalog.objects.create(value="Tpl filter addr")
        self.waste = WasteTypeCatalog.objects.create(code="200301", value="O tpl")
        self.tpl_3h = RideTemplate.objects.create(
            title="Svébořice test",
            vehicle_kind=self.vk_3h,
            name=self.name,
            ico=self.ico,
            address=self.address,
            waste_type=self.waste,
            created_by=self.user,
        )
        self.tpl_3h.applicable_vehicle_kinds.set([self.vk_3h.pk])

    def test_expanded_kind_ids_include_parent_h_for_3h(self):
        expanded = expanded_vehicle_kind_ids_for_template_filter([self.vk_h.pk])
        self.assertIn(self.vk_h.pk, expanded)
        self.assertIn(self.vk_3h.pk, expanded)

    def test_template_3h_matches_filter_by_h(self):
        qs = filter_ride_templates_by_vehicle_kind_ids(
            ride_templates_visible_queryset(self.user),
            [self.vk_h.pk],
        )
        titles = list(qs.values_list("title", flat=True))
        self.assertIn("Svébořice test", titles)

    def test_template_3h_matches_filter_by_3h(self):
        qs = filter_ride_templates_by_vehicle_kind_ids(
            ride_templates_visible_queryset(self.user),
            [self.vk_3h.pk],
        )
        titles = list(qs.values_list("title", flat=True))
        self.assertIn("Svébořice test", titles)
