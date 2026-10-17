import json

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from catalogs.forms import VehicleKindCatalogForm, VehicleRzProfileForm
from catalogs.models import ContainerPassport, VehicleKindCatalog, VehicleRzProfile
from catalogs.services.vehicle_rz_list_search import filter_vehicle_rz_profiles


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


@admin_required
def vehicle_rz_list(request):
    query = (request.GET.get("q") or "").strip()
    items = VehicleRzProfile.objects.select_related("rz").prefetch_related("vehicle_kinds")
    items = filter_vehicle_rz_profiles(items, query)
    return render(request, "catalogs/vehicle_rz_list.html", {"items": items, "q": query})


@admin_required
def vehicle_rz_create(request):
    form = VehicleRzProfileForm(request.POST or None)
    kind_form = VehicleKindCatalogForm()
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:vehicle_rz_list")
    return render(
        request,
        "catalogs/vehicle_rz_form.html",
        {"form": form, "is_edit": False, "kind_form": kind_form},
    )


@admin_required
def vehicle_rz_edit(request, pk):
    item = get_object_or_404(VehicleRzProfile, pk=pk)
    form = VehicleRzProfileForm(request.POST or None, instance=item)
    kind_form = VehicleKindCatalogForm()
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:vehicle_rz_list")
    return render(
        request,
        "catalogs/vehicle_rz_form.html",
        {"form": form, "is_edit": True, "item": item, "kind_form": kind_form},
    )


@admin_required
def vehicle_rz_delete(request, pk):
    item = get_object_or_404(VehicleRzProfile, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:vehicle_rz_list")
    return render(request, "catalogs/vehicle_rz_confirm_delete.html", {"item": item})


@admin_required
def vehicle_kind_list(request):
    items = (
        VehicleKindCatalog.objects.select_related("parent_kind")
        .prefetch_related("child_kinds")
        .order_by("sort_order", "name", "pk")
    )
    return render(request, "catalogs/vehicle_kind_list.html", {"items": items})


@admin_required
@require_POST
def vehicle_kind_reorder(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"ok": False, "error": "Neplatný JSON."}, status=400)
    order = payload.get("order")
    if not isinstance(order, list) or not order:
        return JsonResponse({"ok": False, "error": "Chybí pole order."}, status=400)
    ids = []
    for x in order:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            return JsonResponse({"ok": False, "error": "Neplatné ID."}, status=400)
    with transaction.atomic():
        found = set(VehicleKindCatalog.objects.filter(pk__in=ids).values_list("pk", flat=True))
        if len(found) != len(ids) or len(set(ids)) != len(ids):
            return JsonResponse({"ok": False, "error": "Neplatná nebo duplicitní ID."}, status=400)
        for idx, pk in enumerate(ids):
            VehicleKindCatalog.objects.filter(pk=pk).update(sort_order=idx * 10)
    return JsonResponse({"ok": True})

@admin_required
def vehicle_kind_create(request):
    form = VehicleKindCatalogForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:vehicle_kind_list")
    return render(request, "catalogs/vehicle_kind_form.html", {"form": form, "is_edit": False})


@admin_required
def vehicle_kind_edit(request, pk):
    item = get_object_or_404(VehicleKindCatalog, pk=pk)
    form = VehicleKindCatalogForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:vehicle_kind_list")
    return render(request, "catalogs/vehicle_kind_form.html", {"form": form, "is_edit": True, "item": item})


@admin_required
def vehicle_kind_delete(request, pk):
    item = get_object_or_404(VehicleKindCatalog, pk=pk)
    passport_count = ContainerPassport.objects.filter(vehicle_kind=item).count()
    if request.method == "POST":
        try:
            item.delete()
        except ProtectedError as exc:
            blocked = len(exc.protected_objects)
            messages.error(
                request,
                "Druh vozidla nelze smazat — je na něj navázaná evidence (např. pasporty kontejnerů, jízdy nebo číselníky). "
                f"Počet blokujících záznamů: {blocked}. U pasportů a dalších míst nejdřív nastavte jiný druh vozidla.",
            )
            return redirect("catalogs:vehicle_kind_list")
        return redirect("catalogs:vehicle_kind_list")
    return render(
        request,
        "catalogs/vehicle_kind_confirm_delete.html",
        {"item": item, "container_passport_count": passport_count},
    )


@admin_required
def vehicle_kind_create_ajax(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Neplatná metoda."}, status=405)
    form = VehicleKindCatalogForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "error": "Neplatná data druhu vozidla."}, status=400)
    obj = form.save()
    return JsonResponse(
        {
            "ok": True,
            "data": {"id": obj.pk, "label": str(obj)},
        }
    )
