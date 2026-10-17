"""
Režimy polí průvodky podle činnosti (ActivityFieldRule + výchozí mapa).
"""

from __future__ import annotations

from catalogs.models import ActivityCatalog, ActivityFieldKey, ActivityFieldMode, ActivityFieldRule

# Když pro činnost neexistuje řádek pravidla, použije se tento výchozí režim.
DEFAULT_FIELD_MODES: dict[str, str] = {
    ActivityFieldKey.SUFFIX: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.WASTE_TYPE: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.NAME: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.FULFILLMENT_ADDRESS: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.DRIVER: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.VEHICLE_RZ: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.CONTAINER_1: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTAINER_2: ActivityFieldMode.OFF,
    ActivityFieldKey.CONTACT_PHONE: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTRACT_NUMBER: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.CONTACT_NOTE: ActivityFieldMode.OPTIONAL,
    ActivityFieldKey.SND_CISLO: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.ZPO: ActivityFieldMode.REQUIRED,
    ActivityFieldKey.PIO: ActivityFieldMode.OPTIONAL,
}


def _normalize_activity_id(activity_id: int | None) -> int | None:
    if isinstance(activity_id, bool) or not isinstance(activity_id, int):
        return None
    return activity_id if activity_id > 0 else None


def _rules_map_for_activity(activity_id: int | None) -> dict[str, str]:
    aid = _normalize_activity_id(activity_id)
    if not aid:
        return {}
    rows = ActivityFieldRule.objects.filter(activity_id=aid).values_list("field_key", "mode")
    return {k: v for k, v in rows}


def get_effective_mode(activity_id: int | None, field_key: str) -> str:
    if not _normalize_activity_id(activity_id):
        return DEFAULT_FIELD_MODES.get(field_key, ActivityFieldMode.REQUIRED)
    custom = _rules_map_for_activity(activity_id).get(field_key)
    if custom:
        return custom
    return DEFAULT_FIELD_MODES.get(field_key, ActivityFieldMode.REQUIRED)


def activity_generates_snd(activity_id: int | None) -> bool:
    return get_effective_mode(activity_id, ActivityFieldKey.SND_CISLO) != ActivityFieldMode.OFF


def activity_generates_zpo(activity_id: int | None) -> bool:
    return get_effective_mode(activity_id, ActivityFieldKey.ZPO) != ActivityFieldMode.OFF


def activity_uses_fulfillment_address(activity_id: int | None) -> bool:
    """Zda činnost používá adresu plnění (formulář jízdy i řádek Kde v protokolu STASKA)."""
    aid = _normalize_activity_id(activity_id)
    if not aid:
        return True
    return get_effective_mode(aid, ActivityFieldKey.FULFILLMENT_ADDRESS) != ActivityFieldMode.OFF


_PLACEHOLDER_ADDRESSES = frozenset({"—", "-", "–"})


def protocol_address_snapshot_for_ride(address_snapshot: str, activity_id: int | None) -> str:
    """Hodnota adresy do protokolu jizda.xlsx — prázdná u skryté činnosti nebo placeholderu."""
    if not activity_uses_fulfillment_address(activity_id):
        return ""
    val = (address_snapshot or "").strip()
    if val in _PLACEHOLDER_ADDRESSES:
        return ""
    return val


def activity_rules_for_json(activity_id: int | None) -> dict[str, str]:
    """Všechny známé klíče → efektivní režim (pro formulář / JS)."""
    out: dict[str, str] = {}
    for key in ActivityFieldKey:
        kv = key.value
        out[kv] = (
            get_effective_mode(activity_id, kv)
            if activity_id
            else DEFAULT_FIELD_MODES.get(kv, ActivityFieldMode.REQUIRED)
        )
    return out


def effective_container_slot_count(activity_id: int | None) -> int:
    """1 = v průvodce jen první kontejner; 2 = oba (např. výměna)."""
    if get_effective_mode(activity_id, ActivityFieldKey.CONTAINER_2) == ActivityFieldMode.OFF:
        return 1
    return 2


def apply_mobile_container_slot_choice(activity: ActivityCatalog, slots: int) -> None:
    """
    Synchronizuje ActivityFieldRule pro kontejnery podle volby z editace činnosti.
    Volá se po uložení formsetu pravidel, aby přepisy řádků v tabulce měly přednost,
    kromě cíleného nastavení druhého kontejneru (off vs. povinný).
    """
    aid = activity.pk
    if slots == 1:
        ActivityFieldRule.objects.update_or_create(
            activity_id=aid,
            field_key=ActivityFieldKey.CONTAINER_2,
            defaults={"mode": ActivityFieldMode.OFF},
        )
        return
    if get_effective_mode(aid, ActivityFieldKey.CONTAINER_1) == ActivityFieldMode.OFF:
        ActivityFieldRule.objects.update_or_create(
            activity_id=aid,
            field_key=ActivityFieldKey.CONTAINER_1,
            defaults={"mode": ActivityFieldMode.OPTIONAL},
        )
    ActivityFieldRule.objects.update_or_create(
        activity_id=aid,
        field_key=ActivityFieldKey.CONTAINER_2,
        defaults={"mode": ActivityFieldMode.REQUIRED},
    )
