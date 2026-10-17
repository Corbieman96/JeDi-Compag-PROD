"""Řádky matice požadavků na svoz ze sběrného dvora."""

from __future__ import annotations

from django.db.models import Q

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair


def yard_svoz_matrix_ready_qs(subject: NameSubjectProfile):
    """Řádky jako v matici požadavku: svoz zapnutý, druh vozidla a činnost vyplněné."""
    return (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=subject,
            yard_svoz_enabled=True,
            yard_svoz_activity__isnull=False,
        )
        .filter(Q(yard_vehicle_kinds__isnull=False) | Q(yard_vehicle_kind__isnull=False))
        .distinct()
    )


def yard_pruvodka_pair_exists(subject: NameSubjectProfile) -> bool:
    """
    Aspoň jeden pár má zapnutou průvodku z dvora a činnost (vlastní nebo ze svozu).

    Nepočítá se jen „připravená matice svozu“ — to řídí zvlášť příznak „Povolit matici požadavků“
    a yard_svoz_matrix_row_exists; jinak by jeden řádek omylem otevíral obě cesty.
    """
    return (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=subject,
            yard_pruvodka_enabled=True,
        )
        .filter(_yard_pruvodka_has_activity_q())
        .exists()
    )


def _yard_pruvodka_has_activity_q() -> Q:
    return Q(yard_pruvodka_activity_id__isnull=False) | Q(yard_svoz_activity_id__isnull=False)


def _yard_pruvodka_has_vehicle_kind_q() -> Q:
    return Q(yard_vehicle_kinds__isnull=False) | Q(yard_vehicle_kind__isnull=False)


def yard_pruvodka_matrix_ready_qs(subject: NameSubjectProfile):
    """Řádky pro založení průvodky z dvora: průvodka zapnutá, činnost a druh vozidla."""
    return (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=subject,
            yard_pruvodka_enabled=True,
        )
        .filter(_yard_pruvodka_has_activity_q())
        .filter(_yard_pruvodka_has_vehicle_kind_q())
        .distinct()
    )


def yard_new_date_matrix_ready_qs(subject: NameSubjectProfile):
    """Řádky pro /waste-docs/new/?date — bez zaškrtnuté Svoz (matice), činnost a druh vozidla."""
    return (
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=subject,
            yard_svoz_enabled=False,
        )
        .filter(_yard_pruvodka_has_activity_q())
        .filter(_yard_pruvodka_has_vehicle_kind_q())
        .distinct()
    )


def pruvodka_new_date_pairs_qs(subject: NameSubjectProfile):
    """Řádky F/P pro formulář /waste-docs/new/ — u sběrného dvora jen bez matice svozu."""
    if subject.is_collection_yard:
        return yard_new_date_matrix_ready_qs(subject)
    return NameSubjectWasteSuffixPair.objects.filter(subject_profile=subject)


def yard_pruvodka_matrix_rows(subject: NameSubjectProfile) -> list[NameSubjectWasteSuffixPair]:
    """Řádky na /sberny-dvur/nova-jizda/ — jen s zapnutou „Průvodka z dvora“ a kompletním nastavením."""
    return list(
        yard_pruvodka_matrix_ready_qs(subject)
        .select_related(
            "waste_type",
            "suffix",
            "yard_vehicle_kind",
            "yard_svoz_activity",
            "yard_pruvodka_activity",
        )
        .prefetch_related("yard_vehicle_kinds")
        .order_by("sort_order", "id")
    )


def yard_pruvodka_matrix_stats(subject: NameSubjectProfile) -> dict:
    """Počty pro nápovědu na stránce založení průvodky z dvora."""
    qs = NameSubjectWasteSuffixPair.objects.filter(subject_profile=subject)
    pruvodka_on = qs.filter(yard_pruvodka_enabled=True)
    with_activity = pruvodka_on.filter(_yard_pruvodka_has_activity_q())
    with_vehicle = with_activity.filter(_yard_pruvodka_has_vehicle_kind_q()).distinct()
    missing_kind = with_activity.exclude(_yard_pruvodka_has_vehicle_kind_q()).distinct()
    missing_activity = pruvodka_on.exclude(_yard_pruvodka_has_activity_q()).distinct()
    return {
        "waste_pair_total": qs.count(),
        "pruvodka_enabled_count": pruvodka_on.count(),
        "pruvodka_ready_count": with_vehicle.count(),
        "pruvodka_missing_vehicle_kind": missing_kind.count(),
        "pruvodka_missing_activity": missing_activity.count(),
    }


def yard_svoz_matrix_row_exists(subject: NameSubjectProfile) -> bool:
    """Je připavena aspoň jedna řádka matice požadavku (stejná pravidla jako yard_svoz_matrix_rows)?"""
    return yard_svoz_matrix_ready_qs(subject).exists()


def yard_svoz_matrix_rows(subject: NameSubjectProfile) -> list[NameSubjectWasteSuffixPair]:
    """Řádky zobrazené v matici: vše se zapnutým „Svoz (matice)“, v uživatelském pořadí."""
    return list(
        NameSubjectWasteSuffixPair.objects.filter(
            subject_profile=subject,
            yard_svoz_enabled=True,
        )
        .select_related("waste_type", "suffix", "yard_vehicle_kind", "yard_svoz_activity")
        .prefetch_related("yard_vehicle_kinds")
        .order_by("sort_order", "id")
    )


def yard_svoz_matrix_stats(subject: NameSubjectProfile) -> dict:
    """Počty pro nápovědu na stránce matice (proč je tabulka prázdná)."""
    qs = NameSubjectWasteSuffixPair.objects.filter(subject_profile=subject)
    svoz_on = qs.filter(yard_svoz_enabled=True)
    with_vehicle = svoz_on.filter(
        Q(yard_vehicle_kinds__isnull=False) | Q(yard_vehicle_kind__isnull=False)
    ).distinct()
    missing_kind = svoz_on.exclude(
        Q(yard_vehicle_kinds__isnull=False) | Q(yard_vehicle_kind__isnull=False)
    ).distinct()
    return {
        "waste_pair_total": qs.count(),
        "svoz_enabled_count": svoz_on.count(),
        "svoz_ready_count": with_vehicle.filter(yard_svoz_activity__isnull=False).count(),
        "svoz_missing_vehicle_kind": missing_kind.count(),
        "svoz_missing_activity": with_vehicle.filter(yard_svoz_activity__isnull=True).count(),
    }


def yard_pruvodka_initial_for_subject(subject: NameSubjectProfile) -> dict:
    """Předvyplnění nové průvodky pro uživatele sběrného dvora (bez úkolu svozu)."""
    sub = (
        NameSubjectProfile.objects.filter(pk=subject.pk)
        .select_related("name", "ico", "address_profile__fulfillment_address", "address_profile__facility_address")
        .first()
    )
    if not sub:
        return {}
    parts = []
    if sub.ico and sub.ico.value:
        parts.append(sub.ico.value.strip())
    if sub.name and sub.name.value:
        parts.append(sub.name.value.strip())
    ico_lookup = " ".join(parts) if parts else (sub.company_name or "").strip()
    q = (sub.ico.value if sub.ico_id else "") or ""
    q = (q or "").strip()
    if len(q) < 2:
        q = (sub.name.value if sub.name_id else "") or ""
    q = (q or "").strip()
    if len(q) < 2:
        q = ico_lookup[:120]
    fulfillment_val = ""
    if sub.fulfillment_address_id and sub.fulfillment_address:
        fulfillment_val = sub.fulfillment_address.value
    elif sub.facility_address_id and sub.facility_address:
        fulfillment_val = sub.facility_address.value
    fac_val = ""
    if sub.facility_address_id and sub.facility_address:
        fac_val = sub.facility_address.value
    initial: dict = {}
    if sub.ico_id:
        initial["ico"] = sub.ico_id
    if sub.name_id:
        initial["name"] = sub.name_id
    if fulfillment_val:
        initial["fulfillment_address_value"] = fulfillment_val
    if ico_lookup:
        initial["ico_lookup"] = ico_lookup
    if fac_val:
        initial["facility_address_display"] = fac_val
    phone = (sub.contact_phone or "").strip()
    if phone:
        initial["contact_phone"] = phone
    return initial
