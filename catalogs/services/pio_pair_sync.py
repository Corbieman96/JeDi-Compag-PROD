from __future__ import annotations

from django.db.models import Max
from django.http import QueryDict

from catalogs.models import NameSubjectProfile
from catalogs.models import NameSubjectWasteSuffixPair
from catalogs.services.name_subject_pair_vehicle_kinds import sync_pair_primary_vehicle_kind_fk
from catalogs.services.subject_disposal import sync_subject_allowed_from_pairs
from catalogs.services.subject_satellites import ensure_subject_satellites
from pio.xlsx_generate import resolve_user_pio_waste_and_suffix_from_live_post
from waste_docs.activity_fields import activity_generates_zpo


def _required_zpo_activities(pair: NameSubjectWasteSuffixPair) -> list[int]:
    out: list[int] = []
    if pair.yard_pruvodka_activity_id:
        out.append(int(pair.yard_pruvodka_activity_id))
    if pair.yard_svoz_activity_id:
        out.append(int(pair.yard_svoz_activity_id))
    return out


def _zpo_required_for_pair(profile: NameSubjectProfile, pair: NameSubjectWasteSuffixPair) -> bool:
    # Pokud se ZPO nemá generovat, není potřeba mít vybraný ZPO soubor.
    if pair.suppress_system_zpo:
        return False
    if not profile.system_generates_zpo:
        return False

    activity_ids = _required_zpo_activities(pair)
    if not activity_ids:
        # Aktivita není nastavena → chováme se jako dříve u subjektu (tj. bez tvrdé povinnosti).
        return False
    return any(activity_generates_zpo(aid) for aid in activity_ids)


def _copy_pair_activity_fields(dst: NameSubjectWasteSuffixPair, src: NameSubjectWasteSuffixPair) -> None:
    dst.yard_svoz_enabled = src.yard_svoz_enabled
    dst.yard_pruvodka_enabled = src.yard_pruvodka_enabled
    dst.yard_svoz_activity = src.yard_svoz_activity
    dst.yard_pruvodka_activity = src.yard_pruvodka_activity
    dst.yard_container_kind = src.yard_container_kind
    dst.yard_svoz_display_label = src.yard_svoz_display_label
    dst.yard_dispatch_note_title = src.yard_dispatch_note_title
    dst.yard_dispatch_note_text = src.yard_dispatch_note_text
    dst.yard_dispatch_note_enabled = src.yard_dispatch_note_enabled
    dst.yard_svoz_auto_assign_driver = src.yard_svoz_auto_assign_driver
    dst.yard_svoz_exception_slot = src.yard_svoz_exception_slot
    dst.suppress_system_zpo = src.suppress_system_zpo


def ensure_name_subject_pair_exists_from_pio_live_post(
    profile: NameSubjectProfile, post: QueryDict
) -> NameSubjectWasteSuffixPair:
    """
    PIO (profilová šablona) bere „odpad + koncovku“ z POST a (když je nevyplníte)
    z prvního řádku v „Povolené odpady a koncovky“.

    Tato funkce zajistí, že pro odpad–koncovku existuje odpovídající řádek v
    „Povolené odpady a koncovky“ a že je doplněna logika z „prvního řádku“ i pro
    „druh vozidla“ (yard_vehicle_kinds).

    Pokud aktivita vyžaduje ZPO, vyžaduje se i vybrané ZPO (pair.zpo_id).
    """
    ensure_subject_satellites(profile)

    wt, suf = resolve_user_pio_waste_and_suffix_from_live_post(profile, post)
    if not wt or not suf:
        raise RuntimeError(
            "Chybí druh odpadu a/nebo koncovka pro generování PIO: vyplňte je v sekci PIO."
        )

    # Cílový pár (může existovat, nebo se teprve založí).
    pair = (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=profile,
            waste_type_id=wt.pk,
            suffix_id=suf.pk,
        )
        .prefetch_related("yard_vehicle_kinds")
        .select_related("yard_vehicle_kind", "zpo")
        .first()
    )
    pair_created = pair is None

    # Zdroj pro doplnění „druh vozidla“ a volitelných polí (typicky první řádek).
    if pair is not None:
        source_pair = pair
    else:
        source_pair = (
            NameSubjectWasteSuffixPair.objects.filter(subject_profile=profile)
            .prefetch_related("yard_vehicle_kinds")
            .select_related("yard_vehicle_kind", "zpo")
            .order_by("sort_order", "id")
            .first()
        )

    if pair is None:
        max_sort = (
            NameSubjectWasteSuffixPair.objects.filter(subject_profile=profile).aggregate(m=Max("sort_order")).get("m")
            or 0
        )
        pair = NameSubjectWasteSuffixPair.objects.create(
            subject_profile=profile,
            waste_type=wt,
            suffix=suf,
            sort_order=max_sort + 1,
        )

    # Doplnění „druh vozidla“ a souvisejícího nastavení jen pro nově založený pár.
    if pair_created:
        if source_pair is not None:
            _copy_pair_activity_fields(pair, source_pair)
            pair.save(
                update_fields=[
                    "yard_svoz_enabled",
                    "yard_pruvodka_enabled",
                    "yard_svoz_activity",
                    "yard_pruvodka_activity",
                    "yard_container_kind",
                    "yard_svoz_display_label",
                    "yard_dispatch_note_title",
                    "yard_dispatch_note_text",
                    "yard_dispatch_note_enabled",
                    "yard_svoz_auto_assign_driver",
                    "yard_svoz_exception_slot",
                    "suppress_system_zpo",
                ]
            )
            pair.yard_vehicle_kinds.set(source_pair.yard_vehicle_kinds.all())
        else:
            pair.yard_vehicle_kinds.clear()

    # FK = první vybraný druh v M2M (zachováme existující M2M, opravíme jen FK).
    sync_pair_primary_vehicle_kind_fk(pair)

    # Aktualizace odvozených povolených seznamů (UI a kompatibilní logiky).
    sync_subject_allowed_from_pairs(profile)

    # ZPO povinnost: pokud aktivita vyžaduje ZPO a uživatel ho na páru nemá vybrané,
    # zabráníme generování a upozorníme na nutnost vyplnění v „Povolené odpady a koncovky“.
    if _zpo_required_for_pair(profile, pair) and not pair.zpo_id:
        raise RuntimeError(
            "Chybí ZPO u páru v sekci „Povolené odpady a koncovky“: tento pár by měl generovat ZPO "
            "pro zvolenou činnost/zařízení. Otevřete řádek páru, vyberte ZPO a poté znovu vygenerujte PIO."
        )

    return pair

