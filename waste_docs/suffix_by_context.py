"""Sestavení nabídky koncovek podle odpadu, subjektu a polohy (JSON pro formulář průvodky)."""

from __future__ import annotations

from address_data.services import geocode_address
from catalogs.models import NameSubjectProfile, SuffixCatalog
from waste_docs.pruvodka_services import rank_suffix_sites_for_waste
from waste_docs.yard_matrix import yard_new_date_matrix_ready_qs, yard_svoz_matrix_ready_qs


def suffixes_by_context_payload(get_params) -> dict:
    """
    Vrací slovník vhodný pro JsonResponse: ok, data, filter_note.
    get_params má být request.GET (např. QueryDict).
    """
    waste_type_raw = (get_params.get("waste_type_id") or "").strip()
    name_id_raw = (get_params.get("name_id") or "").strip()
    address_query = (get_params.get("address") or "").strip()
    lat_raw = (get_params.get("lat") or "").strip()
    lng_raw = (get_params.get("lng") or "").strip()
    try:
        waste_type_id = int(waste_type_raw)
    except ValueError:
        return {"ok": True, "data": [], "filter_note": ""}

    yard_pruvodka_only = (get_params.get("yard_pruvodka_only") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    yard_svoz_only = (get_params.get("yard_svoz_matrix_only") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    name_profile = None
    if name_id_raw:
        try:
            name_id_int = int(name_id_raw)
            name_profile = (
                NameSubjectProfile.objects.filter(name_id=name_id_int)
                .prefetch_related(
                    "allowed_waste_types",
                    "allowed_suffixes",
                    "waste_suffix_pairs",
                )
                .first()
            )
        except ValueError:
            name_profile = None

    pair_suffix_ids = None
    if name_profile and (name_profile.waste_suffix_pairs.exists() or name_profile.is_collection_yard):
        if yard_svoz_only:
            pairs = yard_svoz_matrix_ready_qs(name_profile).filter(waste_type_id=waste_type_id)
        elif yard_pruvodka_only or name_profile.is_collection_yard:
            pairs = yard_new_date_matrix_ready_qs(name_profile).filter(waste_type_id=waste_type_id)
        else:
            pairs = name_profile.waste_suffix_pairs.filter(waste_type_id=waste_type_id)
        if not pairs.exists():
            if yard_pruvodka_only or (name_profile.is_collection_yard and not yard_svoz_only):
                note = (
                    "Pro tento druh odpadu nemá subjekt připravený řádek bez „Svoz (matice)“ "
                    "(nezaškrtnutá matice svozu, druh vozidla a činnost). "
                    "Úprava v Číselníky → Názvy F/P osoby."
                )
            elif yard_svoz_only:
                note = (
                    "Pro tento druh odpadu nemá subjekt připravený řádek matice svozu "
                    "(zaškrtnutý „Svoz (matice)“, druh vozidla a činnost u svozu). "
                    "Úprava v Číselníky → Názvy F/P osoby."
                )
            else:
                note = (
                    "Pro tento druh odpadu nemá subjekt definovaný řádek „odpad + koncovka“. "
                    "Doplňte ho v Číselníky → Názvy F/P osoby → úprava subjektu."
                )
            return {"ok": True, "data": [], "filter_note": note}
        pair_suffix_ids = set(pairs.values_list("suffix_id", flat=True))
    elif name_profile:
        allowed_waste_ids = set(name_profile.allowed_waste_types.values_list("id", flat=True))
        if allowed_waste_ids and waste_type_id not in allowed_waste_ids:
            return {
                "ok": True,
                "data": [],
                "filter_note": "Tento druh odpadu není u vybraného subjektu mezi povolenými. Doplňte ho v Číselníky → Názvy F/P osoby → úprava subjektu (Povolené odpady).",
            }

    source_lat = None
    source_lng = None
    if lat_raw and lng_raw:
        try:
            source_lat = float(lat_raw.replace(",", "."))
            source_lng = float(lng_raw.replace(",", "."))
        except ValueError:
            source_lat = None
            source_lng = None

    if source_lat is None or source_lng is None:
        if address_query:
            location = geocode_address(query=address_query)
            if location:
                source_lat = float(location["lat"])
                source_lng = float(location["lng"])

    rows = rank_suffix_sites_for_waste(
        waste_type_id=waste_type_id,
        source_lat=source_lat,
        source_lng=source_lng,
    )
    filter_note = ""
    ranked_by_suffix_id = {int(r["suffix_id"]): r for r in rows}
    pre_suffix_filter = len(rows)
    if name_profile and pair_suffix_ids is not None:
        pair_suffixes = SuffixCatalog.objects.filter(pk__in=pair_suffix_ids).order_by("value")
        rows = []
        for suffix in pair_suffixes:
            ranked = ranked_by_suffix_id.get(int(suffix.pk))
            if ranked:
                rows.append(ranked)
            else:
                rows.append(
                    {
                        "suffix_id": suffix.pk,
                        "suffix_value": suffix.value,
                        "site_name": "",
                        "distance_m": None,
                    }
                )
        if not pre_suffix_filter:
            filter_note = ""
    elif name_profile:
        allowed_suffix_ids = set(name_profile.allowed_suffixes.values_list("id", flat=True))
        if allowed_suffix_ids:
            rows = [r for r in rows if r["suffix_id"] in allowed_suffix_ids]
            if not rows and pre_suffix_filter:
                filter_note = (
                    "Koncovky pro tento odpad jsou v číselníku, ale žádná neodpovídá „Povoleným koncovkám“ u subjektu. Upravte subjekt nebo číselník koncovek."
                )

    data = []
    for row in rows:
        distance_m = row.get("distance_m")
        distance_text = f"{distance_m/1000:.1f} km" if isinstance(distance_m, (int, float)) else ""
        label_parts = [row["suffix_value"]]
        if row.get("site_name"):
            label_parts.append(row["site_name"])
        if distance_text:
            label_parts.append(distance_text)
        data.append(
            {
                "suffix_id": row["suffix_id"],
                "label": " | ".join(label_parts),
                "distance_m": distance_m,
            }
        )
    return {"ok": True, "data": data, "filter_note": filter_note}
