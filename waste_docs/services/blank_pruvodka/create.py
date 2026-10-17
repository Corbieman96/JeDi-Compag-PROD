"""Založení bianko průvodek za den."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from waste_docs.models import Pruvodka
from waste_docs.services.pruvodka_generated_files import regenerate_pruvodka_excel

from .constants import MAX_BLANK_COUNT, ensure_blank_activity_field_rules, get_blank_activity, get_blank_placeholders


class BlankPruvodkaCreateError(ValueError):
    pass


def create_blank_pruvodky(
    *,
    drive_date: date,
    count: int,
    user: AbstractBaseUser,
    note: str = "",
) -> list[Pruvodka]:
    if count < 1 or count > MAX_BLANK_COUNT:
        raise BlankPruvodkaCreateError(f"Počet bianko průvodek musí být 1–{MAX_BLANK_COUNT}.")

    activity = get_blank_activity()
    ensure_blank_activity_field_rules(activity)
    placeholders = get_blank_placeholders()
    note_clean = (note or "").strip()[:200]

    created: list[Pruvodka] = []
    with transaction.atomic():
        for _ in range(count):
            item = Pruvodka(
                activity=activity,
                drive_date=drive_date,
                is_blank_pruvodka=True,
                name=placeholders["name"],
                ico=placeholders["ico"],
                address=placeholders["address"],
                waste_type=placeholders["waste_type"],
                waste_code=placeholders["waste_code"],
                waste_category=placeholders["waste_category"],
                contact_note=note_clean,
                created_by=user,
            )
            item.save()
            created.append(item)

    for item in created:
        regenerate_pruvodka_excel(item)

    return created
