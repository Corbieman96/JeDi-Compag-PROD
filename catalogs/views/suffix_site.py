from django.contrib.auth.decorators import user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from address_data.services import geocode_address, reverse_geocode, suggest_addresses
from catalogs.forms import SuffixSiteProfileForm
from catalogs.models import SuffixSiteProfile, WasteTypeCatalog
from catalogs.services.visoh2 import fetch_subjects_by_ico
from core.models import AppSettings


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


@admin_required
def suffix_site_list(request):
    query = (request.GET.get("q") or "").strip()
    items = SuffixSiteProfile.objects.select_related("suffix", "ico", "address").prefetch_related(
        "accepted_waste_types",
        "produced_waste_types",
    )
    if query:
        items = items.filter(
            Q(suffix__value__icontains=query)
            | Q(name__icontains=query)
            | Q(ico__value__icontains=query)
            | Q(icz__icontains=query)
            | Q(address__value__icontains=query)
            | Q(zuj__icontains=query)
            | Q(accepted_waste_types__value__icontains=query)
            | Q(accepted_waste_types__code__icontains=query)
            | Q(produced_waste_types__value__icontains=query)
            | Q(produced_waste_types__code__icontains=query)
        ).distinct()
    return render(
        request,
        "catalogs/suffix_site_list.html",
        {
            "items": items,
            "q": query,
        },
    )


@admin_required
def suffix_site_create(request):
    form = SuffixSiteProfileForm(request.POST or None, request.FILES or None)
    app_settings = AppSettings.load()
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:suffix_list")
    return render(
        request,
        "catalogs/suffix_site_form.html",
        {
            "form": form,
            "is_edit": False,
            "default_map_lat": app_settings.default_map_lat,
            "default_map_lng": app_settings.default_map_lng,
            "waste_types_empty": not WasteTypeCatalog.objects.exists(),
        },
    )


@admin_required
def suffix_site_edit(request, pk):
    item = get_object_or_404(SuffixSiteProfile, pk=pk)
    form = SuffixSiteProfileForm(request.POST or None, request.FILES or None, instance=item)
    app_settings = AppSettings.load()
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:suffix_list")
    return render(
        request,
        "catalogs/suffix_site_form.html",
        {
            "form": form,
            "is_edit": True,
            "item": item,
            "default_map_lat": app_settings.default_map_lat,
            "default_map_lng": app_settings.default_map_lng,
            "waste_types_empty": not WasteTypeCatalog.objects.exists(),
        },
    )


@admin_required
def suffix_site_delete(request, pk):
    item = get_object_or_404(SuffixSiteProfile, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:suffix_list")
    return render(request, "catalogs/suffix_site_confirm_delete.html", {"item": item})


@admin_required
def visoh2_lookup(request):
    ico = (request.GET.get("ico") or "").strip()
    if not ico:
        return JsonResponse({"ok": False, "error": "Zadejte IČO."}, status=400)
    if not ico.isdigit() or len(ico) != 8:
        return JsonResponse({"ok": False, "error": "IČO musí mít 8 číslic."}, status=400)
    try:
        data = fetch_subjects_by_ico(ico)
    except RuntimeError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=503)
    return JsonResponse({"ok": True, "data": data})


@admin_required
def suffix_address_suggestions(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 3:
        return JsonResponse({"ok": True, "data": []})
    return JsonResponse({"ok": True, "data": suggest_addresses(query=query, limit=6)})


@admin_required
def suffix_address_geocode(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 3:
        return JsonResponse({"ok": False, "error": "Zadejte přesnější adresu."}, status=400)
    location = geocode_address(query=query)
    if not location:
        return JsonResponse({"ok": False, "error": "Adresu se nepodařilo najít."}, status=404)
    return JsonResponse({"ok": True, "data": location})


@admin_required
def suffix_address_reverse_geocode(request):
    lat_raw = (request.GET.get("lat") or "").strip()
    lng_raw = (request.GET.get("lng") or "").strip()
    try:
        lat = float(lat_raw.replace(",", "."))
        lng = float(lng_raw.replace(",", "."))
    except ValueError:
        return JsonResponse({"ok": False, "error": "Neplatné souřadnice."}, status=400)
    location = reverse_geocode(lat=lat, lng=lng)
    if not location:
        return JsonResponse({"ok": False, "error": "Adresu se nepodařilo načíst."}, status=404)
    return JsonResponse({"ok": True, "data": location})
