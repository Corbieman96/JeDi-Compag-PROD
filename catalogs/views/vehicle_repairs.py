"""Evidence oprav vozidla — CRUD pod /catalogs/vehicle-rz/<pk>/repairs/."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalogs.forms.vehicle_repair import VehicleRzRepairForm
from catalogs.models import VehicleRzProfile, VehicleRzRepair
from catalogs.services.vehicle_repairs import month_hours_sum, repairs_for_month, resolve_year_month


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


def _profile_or_404(pk: int) -> VehicleRzProfile:
    return get_object_or_404(VehicleRzProfile.objects.select_related("rz"), pk=pk)


def _parse_year_month(request) -> tuple[int, int]:
    year_raw = (request.GET.get("year") or "").strip()
    month_raw = (request.GET.get("month") or "").strip()
    year = int(year_raw) if year_raw.isdigit() else None
    month = int(month_raw) if month_raw.isdigit() else None
    return resolve_year_month(year=year, month=month)


@admin_required
def vehicle_rz_repair_list(request, pk: int):
    profile = _profile_or_404(pk)
    year, month = _parse_year_month(request)
    items = repairs_for_month(vehicle_rz=profile.rz, year=year, month=month)
    hours_sum = month_hours_sum(vehicle_rz=profile.rz, year=year, month=month)
    return render(
        request,
        "catalogs/vehicle_repair_list.html",
        {
            "profile": profile,
            "items": items,
            "year": year,
            "month": month,
            "hours_sum": hours_sum,
            "month_choices": list(range(1, 13)),
            "year_choices": list(range(year - 3, year + 2)),
        },
    )


@admin_required
def vehicle_rz_repair_create(request, pk: int):
    profile = _profile_or_404(pk)
    form = VehicleRzRepairForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        repair = form.save(commit=False)
        repair.vehicle_rz = profile.rz
        repair.created_by = request.user
        repair.save()
        messages.success(request, "Oprava byla uložena.")
        return redirect(
            reverse("catalogs:vehicle_rz_repair_list", args=[profile.pk])
            + f"?year={repair.repair_date.year}&month={repair.repair_date.month}"
        )
    return render(
        request,
        "catalogs/vehicle_repair_form.html",
        {"form": form, "profile": profile, "is_edit": False},
    )


@admin_required
def vehicle_rz_repair_edit(request, pk: int, repair_pk: int):
    profile = _profile_or_404(pk)
    repair = get_object_or_404(VehicleRzRepair, pk=repair_pk, vehicle_rz=profile.rz)
    form = VehicleRzRepairForm(request.POST or None, instance=repair)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Oprava byla upravena.")
        return redirect(
            reverse("catalogs:vehicle_rz_repair_list", args=[profile.pk])
            + f"?year={repair.repair_date.year}&month={repair.repair_date.month}"
        )
    return render(
        request,
        "catalogs/vehicle_repair_form.html",
        {"form": form, "profile": profile, "is_edit": True, "repair": repair},
    )


@admin_required
def vehicle_rz_repair_delete(request, pk: int, repair_pk: int):
    profile = _profile_or_404(pk)
    repair = get_object_or_404(VehicleRzRepair, pk=repair_pk, vehicle_rz=profile.rz)
    if request.method == "POST":
        year, month = repair.repair_date.year, repair.repair_date.month
        repair.delete()
        messages.success(request, "Oprava byla smazána.")
        return redirect(
            reverse("catalogs:vehicle_rz_repair_list", args=[profile.pk])
            + f"?year={year}&month={month}"
        )
    return render(
        request,
        "catalogs/vehicle_repair_confirm_delete.html",
        {"profile": profile, "repair": repair},
    )
