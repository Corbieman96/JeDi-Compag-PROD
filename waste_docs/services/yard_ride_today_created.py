"""Dnešní průvodky ze sběrného dvora seskupené podle řádku matice (nova-jizda)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.urls import reverse

from catalogs.models import NameSubjectProfile, NameSubjectWasteSuffixPair
from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_generated_files import has_generated_excel_file


def yard_rides_today_by_pair(
    subject: NameSubjectProfile,
    pairs: list[NameSubjectWasteSuffixPair],
    target_date: date,
    *,
    created_by: AbstractBaseUser,
) -> dict[int, list[dict]]:
    """Mapa pair_pk → průvodky založené dnes z nova-jizda (created_by + source_waste_suffix_pair)."""
    if not pairs or not subject.name_id or not subject.ico_id or not created_by:
        return {}

    pair_ids = [int(p.pk) for p in pairs]
    out: dict[int, list[dict]] = {pid: [] for pid in pair_ids}

    rides = (
        Pruvodka.objects.filter(
            drive_date=target_date,
            is_archived=False,
            name_id=subject.name_id,
            ico_id=subject.ico_id,
            created_by=created_by,
            source_waste_suffix_pair_id__in=pair_ids,
        )
        .order_by("-pk")
    )

    for ride in rides:
        pair_id = ride.source_waste_suffix_pair_id
        if pair_id not in out:
            continue

        has_pdf = has_generated_excel_file(ride)
        pdf_url = (
            reverse("waste_docs:ride_pruvodka_pdf", kwargs={"pk": ride.pk}) if has_pdf else ""
        )
        reprint_url = f"{reverse('waste_docs:yard_print_created')}?pks={ride.pk}"

        parts = []
        if (ride.vehicle_rz_snapshot or "").strip():
            parts.append(ride.vehicle_rz_snapshot.strip())
        if (ride.container_number or "").strip():
            parts.append(ride.container_number.strip())
        if (ride.snd_cislo_listu or "").strip():
            parts.append(ride.snd_cislo_listu.strip())

        out[pair_id].append(
            {
                "pk": ride.pk,
                "label": " · ".join(parts) if parts else f"#{ride.pk}",
                "pdf_url": pdf_url,
                "reprint_url": reprint_url,
                "has_pdf": has_pdf,
            }
        )

    return out
