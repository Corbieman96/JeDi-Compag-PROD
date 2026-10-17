"""Zajištění 1:1 satelitních profilů u NameSubjectProfile (kontakt, adresa, dvůr, PIO, ZPO)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from catalogs.models import NameSubjectProfile


def ensure_subject_satellites(profile: NameSubjectProfile) -> None:
    """Vytvoří chybějící satelitní řádky s výchozími hodnotami."""
    if not profile.pk:
        return
    from catalogs.models import (
        SubjectAddressProfile,
        SubjectContactProfile,
        SubjectPioProfile,
        SubjectYardSettings,
        SubjectZpoSettings,
    )

    SubjectContactProfile.objects.get_or_create(
        subject=profile,
        defaults={"contact_phone": "", "contact_note": ""},
    )
    SubjectAddressProfile.objects.get_or_create(
        subject=profile,
        defaults={
            "facility_address_id": None,
            "fulfillment_address_id": None,
            "facility_latitude": None,
            "facility_longitude": None,
            "fulfillment_latitude": None,
            "fulfillment_longitude": None,
            "fulfillment_orp": "",
            "fulfillment_iczuj": "",
        },
    )
    SubjectYardSettings.objects.get_or_create(
        subject=profile,
        defaults={
            "is_collection_yard": False,
            "yard_allow_pruvodka": False,
            "yard_allow_matrix": False,
            "yard_svoz_dispatch_group": "",
            "yard_svoz_ratio_min_containers": 5,
        },
    )
    SubjectPioProfile.objects.get_or_create(
        subject=profile,
        defaults={
            "pio_officer_name": "",
            "pio_officer_phone": "",
            "pio_officer_email": "",
            "pio_outside_map_orp": "",
            "pio_outside_map_iczuj": "",
        },
    )
    SubjectZpoSettings.objects.get_or_create(
        subject=profile,
        defaults={"system_generates_zpo": True},
    )


def save_related_satellites(profile: NameSubjectProfile) -> None:
    """Persistne změny v 1:1 satelitech po úpravě přes property settery."""
    if not profile.pk:
        return
    ensure_subject_satellites(profile)
    profile.contact_profile.save()
    profile.address_profile.save()
    profile.yard_settings.save()
    profile.zpo_settings.save()
    profile.pio_profile.save()


def clear_subject_pio_profile_fields(profile: NameSubjectProfile) -> None:
    """Sekce PIO ve formuláři je jednorázová pro šablonu — po uložení subjektu se profil PIO vymaže."""
    if not profile.pk:
        return
    ensure_subject_satellites(profile)
    pio = profile.pio_profile
    pio.pio_officer_name = ""
    pio.pio_officer_phone = ""
    pio.pio_officer_email = ""
    pio.pio_waste_type_id = None
    pio.pio_suffix_id = None
    pio.pio_outside_map_lat = None
    pio.pio_outside_map_lng = None
    pio.pio_outside_map_orp = ""
    pio.pio_outside_map_iczuj = ""
    pio.save(
        update_fields=[
            "pio_officer_name",
            "pio_officer_phone",
            "pio_officer_email",
            "pio_waste_type",
            "pio_suffix",
            "pio_outside_map_lat",
            "pio_outside_map_lng",
            "pio_outside_map_orp",
            "pio_outside_map_iczuj",
        ]
    )
