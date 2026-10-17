"""Konstanty a číselníky pro bianko průvodky."""

from __future__ import annotations

from catalogs.models import (
    ActivityCatalog,
    ActivityFieldKey,
    ActivityFieldMode,
    ActivityFieldRule,
    AddressCatalog,
    IcoCatalog,
    NameCatalog,
    WasteCategoryCatalog,
    WasteCodeCatalog,
    WasteTypeCatalog,
)

BLANK_ACTIVITY_NAME = "Bianko průvodka"
BLANK_NAME_VALUE = "Bianko — doplnit později"
BLANK_ICO_VALUE = "00000000"
BLANK_ADDRESS_VALUE = "—"
BLANK_WASTE_TYPE_VALUE = "Bianko"
BLANK_WASTE_CODE_VALUE = "000000"
BLANK_WASTE_CATEGORY_VALUE = "—"
DEFAULT_ARCHIVE_REASON = "Bianko — nejelo se / nepoužito"
MAX_BLANK_COUNT = 50

_BLANK_FIELD_RULES: dict[str, str] = {
    ActivityFieldKey.SND_CISLO: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.ZPO: ActivityFieldMode.OFF,
    ActivityFieldKey.PIO: ActivityFieldMode.OFF,
    ActivityFieldKey.SUFFIX: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.WASTE_TYPE: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.NAME: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.FULFILLMENT_ADDRESS: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.DRIVER: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.VEHICLE_RZ: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTAINER_1: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTAINER_2: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTACT_PHONE: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTRACT_NUMBER: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTACT_NOTE: ActivityFieldMode.OPTIONAL,
}


def get_blank_activity() -> ActivityCatalog:
    activity, _ = ActivityCatalog.objects.get_or_create(
        name=BLANK_ACTIVITY_NAME,
        defaults={
            "visible_for_submitter": False,
            "require_nitropodnikovy_subjekt": False,
            "evidence_without_excel": False,
        },
    )
    return activity


def ensure_blank_activity_field_rules(activity: ActivityCatalog) -> None:
    for field_key, mode in _BLANK_FIELD_RULES.items():
        ActivityFieldRule.objects.update_or_create(
            activity=activity,
            field_key=field_key,
            defaults={"mode": mode},
        )


def get_blank_activity_id() -> int | None:
    return ActivityCatalog.objects.filter(name=BLANK_ACTIVITY_NAME).values_list("pk", flat=True).first()


def is_blank_pruvodka_activity(activity_id: int | None) -> bool:
    blank_id = get_blank_activity_id()
    return bool(blank_id and activity_id == blank_id)


def is_blank_pruvodka_ride(ride) -> bool:
    if getattr(ride, "is_blank_pruvodka", False):
        return True
    return is_blank_pruvodka_activity(getattr(ride, "activity_id", None))


def get_blank_placeholders() -> dict:
    name, _ = NameCatalog.objects.get_or_create(value=BLANK_NAME_VALUE)
    ico, _ = IcoCatalog.objects.get_or_create(value=BLANK_ICO_VALUE)
    address, _ = AddressCatalog.objects.get_or_create(value=BLANK_ADDRESS_VALUE)
    waste_type, _ = WasteTypeCatalog.objects.get_or_create(
        code=BLANK_WASTE_CODE_VALUE,
        defaults={"value": BLANK_WASTE_TYPE_VALUE, "category": BLANK_WASTE_CATEGORY_VALUE},
    )
    waste_code, _ = WasteCodeCatalog.objects.get_or_create(value=BLANK_WASTE_CODE_VALUE)
    waste_category, _ = WasteCategoryCatalog.objects.get_or_create(value=BLANK_WASTE_CATEGORY_VALUE)
    return {
        "name": name,
        "ico": ico,
        "address": address,
        "waste_type": waste_type,
        "waste_code": waste_code,
        "waste_category": waste_category,
    }
