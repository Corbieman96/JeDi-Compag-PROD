"""Číslování jízd (skupina, sekvence, snd_cislo_listu) a snapshoty katalogů před uložením průvodky."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models, transaction
from django.utils import timezone

from waste_docs.activity_fields import activity_generates_snd

if TYPE_CHECKING:
    from waste_docs.models import Pruvodka


def format_snd(group_number: int, year: int, sequence: int) -> str:
    return f"{group_number:07d}-{year}-{sequence}"


def _has_assigned_snd(instance: Pruvodka) -> bool:
    return bool((instance.snd_cislo_listu or "").strip())


def freeze_assigned_ride_number(instance: Pruvodka) -> None:
    """Obnoví neměnné číslo jízdy z databáze (pojistka proti přepsání při editaci)."""
    from waste_docs.models import Pruvodka

    if instance._state.adding or not instance.pk:
        return
    stored = (
        Pruvodka.objects.filter(pk=instance.pk)
        .values("snd_cislo_listu", "ride_group_number", "ride_sequence")
        .first()
    )
    if not stored:
        return
    snd = (stored["snd_cislo_listu"] or "").strip()
    if not snd:
        return
    instance.snd_cislo_listu = snd
    instance.ride_group_number = int(stored["ride_group_number"] or 0)
    instance.ride_sequence = int(stored["ride_sequence"] or 1)


def _needs_snd_assignment(instance: Pruvodka) -> bool:
    """Přidělit SND jen nové jízdě nebo záznamu, který ho ještě nemá.

    U existující jízdy s číslem listu se SND nemění — ani při úpravě data, řidiče
    nebo RZ (unikátní číslo je neměnné).
    """
    if instance._state.adding:
        return True
    return not (instance.snd_cislo_listu or "").strip()


def assign_ride_number_fields(instance: Pruvodka) -> None:
    from waste_docs.models import Pruvodka
    from waste_docs.services.blank_pruvodka.constants import is_blank_pruvodka_ride

    if not instance._state.adding and _has_assigned_snd(instance):
        return

    gen_snd = activity_generates_snd(instance.activity_id)
    if (
        gen_snd
        and is_blank_pruvodka_ride(instance)
        and _needs_snd_assignment(instance)
    ):
        year = instance.drive_date.year
        with transaction.atomic():
            year_qs = Pruvodka.objects.filter(
                drive_date__year=year,
                ride_group_number__gt=0,
            )
            if instance.pk:
                year_qs = year_qs.exclude(pk=instance.pk)
            max_group = int(year_qs.aggregate(m=models.Max("ride_group_number")).get("m") or 0)
            instance.ride_group_number = max_group + 1
            instance.ride_sequence = 1
            instance.snd_cislo_listu = format_snd(instance.ride_group_number, year, instance.ride_sequence)
        return
    if gen_snd and instance.vehicle_rz_id and _needs_snd_assignment(instance):
        year = instance.drive_date.year
        with transaction.atomic():
            base_day_qs = Pruvodka.objects.filter(drive_date=instance.drive_date, ride_group_number__gt=0)
            if instance.pk:
                base_day_qs = base_day_qs.exclude(pk=instance.pk)

            year_qs = Pruvodka.objects.filter(
                drive_date__year=year,
                ride_group_number__gt=0,
            )
            if instance.pk:
                year_qs = year_qs.exclude(pk=instance.pk)
            max_group = int(year_qs.aggregate(m=models.Max("ride_group_number")).get("m") or 0)

            # Skupina = řidič + RZ + den (soulad s protokolem a dashboardem).
            if instance.driver_id:
                same_ride_group_qs = base_day_qs.filter(
                    driver_id=instance.driver_id,
                    vehicle_rz_id=instance.vehicle_rz_id,
                )
            else:
                same_ride_group_qs = base_day_qs.filter(
                    vehicle_rz_id=instance.vehicle_rz_id,
                    driver_id__isnull=True,
                )
            existing_group = (
                same_ride_group_qs.order_by("-created_at", "-pk")
                .values_list("ride_group_number", flat=True)
                .first()
            )
            group_number = int(existing_group) if existing_group else (max_group + 1)

            instance.ride_group_number = group_number
            current_max_seq = int(
                base_day_qs.filter(ride_group_number=group_number).aggregate(m=models.Max("ride_sequence")).get("m")
                or 0
            )
            instance.ride_sequence = current_max_seq + 1
            instance.snd_cislo_listu = format_snd(group_number, year, instance.ride_sequence)
    elif not gen_snd:
        # U existující jízdy s přiděleným SND číslo nikdy nemazat (změna činnosti).
        if instance._state.adding and not _has_assigned_snd(instance):
            instance.ride_group_number = 0
            instance.ride_sequence = 1
            instance.snd_cislo_listu = ""


def apply_pruvodka_catalog_snapshots(instance: Pruvodka) -> None:
    from waste_docs.activity_fields import activity_uses_fulfillment_address, protocol_address_snapshot_for_ride
    from waste_docs.services.blank_pruvodka.archive import is_unused_blank_pruvodka

    if is_unused_blank_pruvodka(instance):
        instance.name_snapshot = ""
        instance.ico_snapshot = ""
        instance.address_snapshot = ""
        instance.waste_type_snapshot = ""
        instance.waste_code_snapshot = ""
        instance.waste_category_snapshot = ""
        instance.vehicle_rz_snapshot = ""
        instance.driver_snapshot = ""
        instance.contract_number_snapshot = ""
        instance.suffix_snapshot = ""
        instance.weight_snapshot = ""
        if instance.activity_id:
            instance.activity_snapshot = instance.activity.name
        return

    if instance.name_id:
        instance.name_snapshot = instance.name.value
    if instance.activity_id:
        instance.activity_snapshot = instance.activity.name
    if instance.ico_id:
        instance.ico_snapshot = instance.ico.value
    if instance.address_id and activity_uses_fulfillment_address(instance.activity_id):
        instance.address_snapshot = protocol_address_snapshot_for_ride(
            instance.address.value,
            instance.activity_id,
        )
    else:
        instance.address_snapshot = ""
    if instance.waste_type_id:
        instance.waste_type_snapshot = instance.waste_type.value
    if instance.waste_code_id:
        instance.waste_code_snapshot = instance.waste_code.value
    if instance.waste_category_id:
        instance.waste_category_snapshot = instance.waste_category.value
    if instance.vehicle_rz_id:
        instance.vehicle_rz_snapshot = instance.vehicle_rz.value
    if instance.driver_id:
        full_name = " ".join(
            part for part in [instance.driver.title, instance.driver.first_name, instance.driver.last_name] if part
        ).strip()
        instance.driver_snapshot = full_name or instance.driver.personal_number
    instance.contract_number_snapshot = (instance.contract_number or "").strip()
    if instance.suffix_id:
        instance.suffix_snapshot = instance.suffix.value
    else:
        instance.suffix_snapshot = ""
    cn2 = (instance.container_number_2 or "").strip()
    instance.container_snapshot_2 = cn2
    if instance.weight_t is not None:
        from waste_docs.services.weight_input import format_weight_snapshot

        instance.weight_snapshot = format_weight_snapshot(instance.weight_t)
    else:
        instance.weight_snapshot = ""


def apply_pruvodka_pre_save(instance: Pruvodka) -> None:
    if not instance.drive_date:
        instance.drive_date = timezone.localdate()
    freeze_assigned_ride_number(instance)
    assign_ride_number_fields(instance)
    freeze_assigned_ride_number(instance)
    apply_pruvodka_catalog_snapshots(instance)
