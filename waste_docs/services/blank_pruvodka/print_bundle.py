"""Tisk bianko průvodek — sestavení souborů a parsování výběru."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from users.services.access import can_see_all_waste_docs
from waste_docs.models import Pruvodka
from waste_docs.services.print_bundle_prepare import print_prepare_context
from waste_docs.services.ride_bulk_actions import build_print_rows_and_files
from waste_docs.ride_print_service import build_ride_print_rows
from waste_docs.services.ride_print_order import order_rides_queryset


def parse_blank_print_pks(*, pks_raw: str = "", pk_raw: str = "") -> list[int]:
    raw = (pks_raw or "").strip() or (pk_raw or "").strip()
    if not raw:
        return []
    try:
        return [int(p) for p in raw.split(",") if p.strip().isdigit()]
    except ValueError:
        return []


def rides_for_blank_print(pks: list[int], user: AbstractBaseUser) -> list[Pruvodka]:
    if not pks:
        return []
    rides_qs = order_rides_queryset(
        Pruvodka.objects.filter(pk__in=pks, is_archived=False, is_blank_pruvodka=True).select_related("activity")
    )
    if not can_see_all_waste_docs(user):
        rides_qs = rides_qs.filter(created_by=user)
    return list(rides_qs)


def build_blank_print_file_rows(
    pks: list[int],
    user: AbstractBaseUser,
) -> tuple[list[dict], list[dict], list[str], dict[str, object]]:
    rides = rides_for_blank_print(pks, user)
    if not rides:
        return [], [], [], print_prepare_context([])
    prepare_ctx = print_prepare_context(rides, include_zpo=False)
    if prepare_ctx["needs_print_prepare"]:
        return build_ride_print_rows(rides), [], [], prepare_ctx
    print_rows, file_rows, zpo_warnings = build_print_rows_and_files(rides)
    return print_rows, file_rows, zpo_warnings, prepare_ctx
