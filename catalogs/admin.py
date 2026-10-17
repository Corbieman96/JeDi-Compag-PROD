from django.contrib import admin

from .models import (
    AddressCatalog,
    ActivityCatalog,
    DriverProfile,
    IcoCatalog,
    NameCatalog,
    NameSubjectProfile,
    SubjectAddressProfile,
    SubjectContactProfile,
    SubjectPioProfile,
    SubjectYardSettings,
    SubjectZpoSettings,
    SuffixCatalog,
    SuffixSiteProfile,
    VehicleKindCatalog,
    VehicleRzCatalog,
    VehicleRzProfile,
    VehicleRzRepair,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
    ZpoDocument,
)


@admin.register(ZpoDocument)
class ZpoDocumentAdmin(admin.ModelAdmin):
    list_display = ("label", "waste_type", "suffix", "file")
    search_fields = ("label",)
    list_filter = ("suffix", "waste_type")


@admin.register(NameCatalog, IcoCatalog, AddressCatalog, WasteCodeCatalog, WasteCategoryCatalog, VehicleRzCatalog, SuffixCatalog)
class SimpleCatalogAdmin(admin.ModelAdmin):
    list_display = ("value",)
    search_fields = ("value",)


@admin.register(WasteTypeCatalog)
class WasteTypeCatalogAdmin(admin.ModelAdmin):
    list_display = ("code", "value", "category")
    search_fields = ("code", "value", "category", "description_fo", "description_po")


class SubjectAddressInline(admin.StackedInline):
    model = SubjectAddressProfile
    fk_name = "subject"
    can_delete = False
    max_num = 1
    min_num = 1


class SubjectSatelliteInline(admin.StackedInline):
    """Sdílená základna pro 1:1 satelity s subject jako PK."""

    fk_name = "subject"
    can_delete = False
    max_num = 1
    min_num = 1


class SubjectContactInline(SubjectSatelliteInline):
    model = SubjectContactProfile


class SubjectYardInline(SubjectSatelliteInline):
    model = SubjectYardSettings


class SubjectZpoInline(SubjectSatelliteInline):
    model = SubjectZpoSettings


class SubjectPioInline(SubjectSatelliteInline):
    model = SubjectPioProfile


@admin.register(NameSubjectProfile)
class NameSubjectProfileAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "name",
        "ico",
        "facility_latitude_admin",
        "facility_longitude_admin",
        "fulfillment_latitude_admin",
        "fulfillment_longitude_admin",
    )
    search_fields = ("company_name", "name__value", "ico__value")
    filter_horizontal = ("allowed_waste_types", "allowed_suffixes")
    inlines = (
        SubjectContactInline,
        SubjectAddressInline,
        SubjectYardInline,
        SubjectZpoInline,
        SubjectPioInline,
    )

    @admin.display(description="Prov. lat")
    def facility_latitude_admin(self, obj: NameSubjectProfile):
        return obj.facility_latitude

    @admin.display(description="Prov. lng")
    def facility_longitude_admin(self, obj: NameSubjectProfile):
        return obj.facility_longitude

    @admin.display(description="Plnění lat")
    def fulfillment_latitude_admin(self, obj: NameSubjectProfile):
        return obj.fulfillment_latitude

    @admin.display(description="Plnění lng")
    def fulfillment_longitude_admin(self, obj: NameSubjectProfile):
        return obj.fulfillment_longitude


@admin.register(SuffixSiteProfile)
class SuffixSiteProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "suffix", "ico", "icz", "facility_type", "zuj", "latitude", "longitude")
    search_fields = ("name", "suffix__value", "ico__value", "icz", "facility_type", "zuj")
    filter_horizontal = ("accepted_waste_types", "produced_waste_types")


class VehicleKindChildInline(admin.TabularInline):
    model = VehicleKindCatalog
    fk_name = "parent_kind"
    extra = 0
    verbose_name = "Podřízený druh"
    verbose_name_plural = "Podřízené druhy"
    fields = ("name", "shortcut", "sort_order")
    show_change_link = True


@admin.register(VehicleKindCatalog)
class VehicleKindCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "shortcut", "parent_kind", "child_kinds_short")
    search_fields = ("name", "shortcut")
    filter_horizontal = ("extra_compatible_kinds",)
    autocomplete_fields = ("parent_kind",)
    inlines = (VehicleKindChildInline,)

    @admin.display(description="Podřízené")
    def child_kinds_short(self, obj):
        labels = [c.display_label() for c in obj.child_kinds.all()[:5]]
        return ", ".join(labels) if labels else "—"


@admin.register(VehicleRzProfile)
class VehicleRzProfileAdmin(admin.ModelAdmin):
    list_display = ("rz", "vehicle_type", "has_trailer", "has_crane")
    search_fields = ("rz__value", "vehicle_type")
    filter_horizontal = ("vehicle_kinds",)


@admin.register(VehicleRzRepair)
class VehicleRzRepairAdmin(admin.ModelAdmin):
    list_display = ("vehicle_rz", "repair_date", "hours", "note", "created_by")
    search_fields = ("vehicle_rz__value", "note")
    list_filter = ("repair_date",)


@admin.register(ActivityCatalog)
class ActivityCatalogAdmin(admin.ModelAdmin):
    list_display = ("name", "default_service_minutes")
    search_fields = ("name",)
    filter_horizontal = ("vehicle_kinds",)


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("personal_number", "phone", "job_position", "employment_type")
    search_fields = ("personal_number", "phone", "job_position", "driver_license_number")
    filter_horizontal = ("allowed_vehicle_rz", "allowed_vehicle_kinds")
