"""CRUD pasportů kontejnerů."""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from catalogs.catalog_nav_registry import SLUG_CONTAINER_PASSPORT
from catalogs.forms.container_passport import ContainerPassportForm
from catalogs.models import ContainerPassport, PasportStredisko, VehicleKindCatalog
from catalogs.services.container_passport_history import (
    HISTORY_LIMIT,
    container_passport_ride_history,
)
from users.decorators import catalogs_nav_required
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from waste_docs.models import Pruvodka


def _require_container_passport_catalog_visible(user):
    return user.is_authenticated and effective_show_catalog_index_row(user, SLUG_CONTAINER_PASSPORT)


def container_passport_catalog_visible(view):
    return user_passes_test(_require_container_passport_catalog_visible)(view)


admin_required = user_passes_test(lambda u: u.is_authenticated and u.is_superuser)


@catalogs_nav_required
@container_passport_catalog_visible
def container_passport_list(request):
    qs = ContainerPassport.objects.select_related("vehicle_kind", "stredisko").order_by(
        "vehicle_kind__sort_order",
        "vehicle_kind__name",
        "vehicle_kind_id",
        "container_number",
    )
    cislo = (request.GET.get("cislo") or "").strip()
    if cislo:
        qs = qs.filter(container_number__icontains=cislo)

    stredisko_raw = (request.GET.get("stredisko") or "").strip()
    stredisko_id = int(stredisko_raw) if stredisko_raw.isdigit() else None
    if stredisko_id is not None:
        qs = qs.filter(stredisko_id=stredisko_id)

    kind_pk = (request.GET.get("vehicle_kind") or "").strip()
    filter_vehicle_kind_id = int(kind_pk) if kind_pk.isdigit() else None
    if filter_vehicle_kind_id is not None:
        qs = qs.filter(vehicle_kind_id=filter_vehicle_kind_id)

    has_filters = bool(cislo) or (stredisko_id is not None) or (filter_vehicle_kind_id is not None)

    latest_by_pk = {}
    open_rides = (
        Pruvodka.objects.filter(is_archived=False, container_passport_id__isnull=False)
        .select_related("container_passport")
        .order_by("-drive_date", "-pk")
    )
    for ride in open_rides:
        cid = ride.container_passport_id
        if cid and cid not in latest_by_pk:
            latest_by_pk[cid] = ride
    items_list = list(qs)
    for row in items_list:
        setattr(row, "latest_ride", latest_by_pk.get(row.pk))

    create_params = {}
    if filter_vehicle_kind_id is not None:
        create_params["vehicle_kind"] = str(filter_vehicle_kind_id)
    create_querystring = urlencode(create_params)

    return render(
        request,
        "catalogs/container_passport_list.html",
        {
            "items": items_list,
            "filter_cislo": cislo,
            "filter_stredisko_id": stredisko_id,
            "filter_vehicle_kind_id": filter_vehicle_kind_id,
            "has_filters": has_filters,
            "create_querystring": create_querystring,
            "results_count": len(items_list),
            "vehicle_kind_options": VehicleKindCatalog.objects.order_by("sort_order", "name", "pk"),
            "stredisko_options": PasportStredisko.objects.filter(is_active=True).order_by("sort_order", "code", "pk"),
        },
    )


@catalogs_nav_required
@container_passport_catalog_visible
def container_passport_history(request, pk):
    item = get_object_or_404(
        ContainerPassport.objects.select_related("vehicle_kind", "stredisko"), pk=pk
    )
    rides = container_passport_ride_history(item)
    return render(
        request,
        "catalogs/container_passport_history.html",
        {
            "item": item,
            "rides": rides,
            "results_count": len(rides),
            "history_limit": HISTORY_LIMIT,
            "history_truncated": len(rides) >= HISTORY_LIMIT,
        },
    )


@catalogs_nav_required
@admin_required
def container_passport_create(request):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    initial = {}
    raw_kind = (request.GET.get("vehicle_kind") or "").strip()
    if raw_kind.isdigit():
        initial["vehicle_kind"] = int(raw_kind)
    form = ContainerPassportForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:container_passport_list")
    return render(request, "catalogs/container_passport_form.html", {"form": form, "is_edit": False})


@catalogs_nav_required
@admin_required
def container_passport_edit(request, pk):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    item = get_object_or_404(ContainerPassport, pk=pk)
    form = ContainerPassportForm(request.POST or None, request.FILES or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:container_passport_list")
    return render(
        request,
        "catalogs/container_passport_form.html",
        {"form": form, "is_edit": True, "item": item},
    )


@catalogs_nav_required
@admin_required
def container_passport_delete(request, pk):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    item = get_object_or_404(ContainerPassport, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:container_passport_list")
    return render(request, "catalogs/container_passport_confirm_delete.html", {"item": item})
