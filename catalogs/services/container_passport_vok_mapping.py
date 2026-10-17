"""Převodník hodnot z VOK / tabulky na zkratku druhu vozidla a odvozené poznámky."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

# Požadavek na vozidlo u kontejneru 40′ (např. třínápravové / 3H)
VEHICLE_REQUIREMENT_FOR_40FT = "3H"
# Od tohoto objemu (m³) se při importu VOK doplní stejná poznámka jako u velkých kontejnerů (3H).
VEHICLE_REQUIREMENT_M3_THRESHOLD = Decimal("30")

# Výchozí mapa: normalizovaný název listu VOK (viz ``shortcut_from_sheet_name``) → zkratka v
# ``VehicleKindCatalog`` (/catalogs/vehicle-rz/kinds/). Hodnota musí v DB existovat (odpovídá i jiné velikosti písmen).
# Přepíše / rozšíří ``settings.VOK_IMPORT_SHEET_KIND_MAP``.
#
# Pravidla dle provozu:
# - list ``100_VOK`` = řetěz — pokud máte v číselníku zkratku ``100_VOK``, mapování nepotřebujete; jinak doplňte pár např. ``"100_VOK": "V"``.
# - ``200_ABROLL`` a ``400_BPS`` → zkratka **A**
# - ``300_ATEGO`` a ``600_VOK`` → zkratka **h** (hák; v DB často **H** — dopárování je case-insensitive)
VOK_SHEET_NAME_TO_KIND_SHORTCUT: dict[str, str] = {
    "200_ABROLL": "A",
    "300_ATEGO": "h",
    "400_BPS": "A",
    "600_VOK": "h",
}


def _strip_marks(s: str) -> str:
    n = unicodedata.normalize("NFD", (s or "").strip().lower())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def resolve_vehicle_kind_shortcut(vok_or_type_raw: str) -> str:
    """
    Vrací zkratku v číselníku druhů vozidel (VehicleKindCatalog.shortcut).

    Pravidla (dle zadání):
    - 100_VOK / řetěz → ``100_VOK``
    - Hák, Atego a obdobné → ``300_ATEGO``
    - Jinak: pokud řetěz vypadá jako už hotová zkratka (např. ``300_ATEGO``), vrátí se znormalizovaná verze.
    """
    raw = (vok_or_type_raw or "").strip()
    if not raw:
        raise ValueError("Prázdný typ vozidla / VOK.")

    s = _strip_marks(raw)
    s_compact = re.sub(r"[\s\-]+", "_", s)

    if "100" in s and "vok" in s:
        return "100_VOK"
    if s_compact == "100_vok" or raw.strip().upper() == "100_VOK":
        return "100_VOK"
    if "vok" in s and ("retez" in s or "retaz" in s):
        return "100_VOK"

    if "atego" in s or "hak" in s or "hook" in s:
        return "300_ATEGO"

    up = raw.strip().upper().replace(" ", "_")
    # Jen „strukturované“ zkratky (číslice nebo podtržítko), ne libovolné slovo z buňky Typ (VANA, …).
    if re.match(r"^[A-Z0-9_]{2,20}$", up) and (re.search(r"[0-9]", up) or "_" in up):
        return up

    raise ValueError(f"Neznámý typ vozidla / VOK: {raw!r}")


def shortcut_from_sheet_name(sheet_name: str) -> str | None:
    """
    Z názvu listu (např. ``100_VOK``, ``300_ATEGO_(AVIA)``) odvodí klíč pro mapování na zkratku v číselníku.
    """
    base = (sheet_name or "").strip().split("(")[0].strip().rstrip("_").upper().replace(" ", "_")
    if re.match(r"^[A-Z0-9_]{2,40}$", base):
        return base
    return None


def merged_vok_sheet_kind_aliases() -> dict[str, str]:
    """Sloučení výchozí mapy a ``settings.VOK_IMPORT_SHEET_KIND_MAP``."""
    from django.conf import settings

    out = dict(VOK_SHEET_NAME_TO_KIND_SHORTCUT)
    extra = getattr(settings, "VOK_IMPORT_SHEET_KIND_MAP", None)
    if isinstance(extra, dict):
        for k, v in extra.items():
            sk = shortcut_from_sheet_name(str(k).strip())
            if sk and v is not None and str(v).strip():
                out[sk] = str(v).strip()
    return out


def canonical_vehicle_kind_shortcut(wanted: str | None, catalog_shortcuts: frozenset[str]) -> str | None:
    """Vrátí zkratku z ``catalog_shortcuts`` přesnou nebo se stejným textem bez ohledu na velikost písmen."""
    if not wanted:
        return None
    if wanted in catalog_shortcuts:
        return wanted
    w = wanted.casefold()
    for c in catalog_shortcuts:
        if c.casefold() == w:
            return c
    return None


def resolve_vok_import_to_catalog_shortcut(
    sheet_name: str,
    vok_cell_raw: str,
    *,
    catalog_shortcuts: frozenset[str],
) -> str | None:
    """
    Vrátí ``VehicleKindCatalog.shortcut``, který skutečně existuje v ``catalog_shortcuts``.

    Pořadí: alias z mapy pro list (aby VOK list nepřebil cílový druh vozidla) → přesná shoda názvu listu
    (vč. casefold) → buňka Typ.
    """
    sheet_key = shortcut_from_sheet_name(sheet_name)
    aliases = merged_vok_sheet_kind_aliases()

    if sheet_key:
        mapped = aliases.get(sheet_key)
        if mapped:
            hit = canonical_vehicle_kind_shortcut(mapped, catalog_shortcuts)
            if hit:
                return hit
        hit = canonical_vehicle_kind_shortcut(sheet_key, catalog_shortcuts)
        if hit:
            return hit

    cell = (vok_cell_raw or "").strip()
    if cell:
        try:
            cell_key = resolve_vehicle_kind_shortcut(cell)
        except ValueError:
            cell_key = None
        hit = canonical_vehicle_kind_shortcut(cell_key, catalog_shortcuts)
        if hit:
            return hit
    return None


def parse_container_size_ft(raw: str | int | float | None) -> int | None:
    """Vrátí 20 nebo 40 z buňky, jinak None."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw in (20, 40):
            return int(raw)
        return None
    t = _strip_marks(str(raw))
    m = re.search(r"\b(20|40)\b", t)
    if m:
        return int(m.group(1))
    return None


def vehicle_requirement_for_size_ft(size_ft: int | None) -> str:
    if size_ft == 40:
        return VEHICLE_REQUIREMENT_FOR_40FT
    return ""


def parse_volume_m3(raw: str | int | float | None) -> Decimal | None:
    """Parsuje objem v m³ z buňky (např. ``7,00``, ``22``)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw if raw > 0 else None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw <= 0:
            return None
        return Decimal(str(raw))
    t = str(raw).strip().replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        d = Decimal(t)
    except InvalidOperation:
        return None
    if d <= 0:
        return None
    return d


def vehicle_requirement_for_volume_m3(volume_m3: Decimal | None) -> str:
    if volume_m3 is not None and volume_m3 >= VEHICLE_REQUIREMENT_M3_THRESHOLD:
        return VEHICLE_REQUIREMENT_FOR_40FT
    return ""
