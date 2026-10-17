"""Nápovědy pro combobox RZ na stránce plánu svozů (konflikt s průvodkami × duplicity v plánu)."""

from __future__ import annotations

from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka, SvozYardDriverPlan


def vehicle_rz_ids_with_pruvodka_on_date(plan_date: date, *, user: AbstractBaseUser) -> frozenset[int]:
    """
    RZ, která mají v daný den alespoň jednu nearchivovanou průvodku.
    Pro ne-dispečerské uživatele (pro jistotu) stejný filtr jako u seznamu jízd vlastní práce —
    při přístupu k plánu svozů je ale view již omezené jen na široké role.
    """
    qs = Pruvodka.objects.filter(drive_date=plan_date, is_archived=False).exclude(vehicle_rz_id__isnull=True)
    if user.is_authenticated and not can_see_all_waste_docs(user):
        qs = qs.filter(created_by=user)
    return frozenset(qs.values_list("vehicle_rz_id", flat=True).distinct())


def vehicle_rz_ids_multi_assigned_in_plan(plan_date: date) -> frozenset[int]:
    """RZ použité ve více řádcích plánu (SvozYardDriverPlan) v jeden den — potenciální dvojí obsazení slotu."""
    rows = (
        SvozYardDriverPlan.objects.filter(plan_date=plan_date, vehicle_rz_id__isnull=False)
        .values("vehicle_rz_id")
        .annotate(c=Count("pk"))
        .filter(c__gt=1)
    )
    return frozenset(int(r["vehicle_rz_id"]) for r in rows)