from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from address_data.services import geocode_address, reverse_geocode, suggest_addresses


@login_required
def address_suggestions(request):
    query = (request.GET.get("q") or "").strip()
    preferred_city = (request.GET.get("preferred_city") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": True, "data": []})
    suggestions = suggest_addresses(query=query, limit=8, preferred_city=preferred_city)
    return JsonResponse({"ok": True, "data": suggestions})


@login_required
def address_geocode(request):
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return JsonResponse({"ok": False, "error": "Zadejte přesnější adresu."}, status=400)
    location = geocode_address(query=query)
    if not location:
        return JsonResponse({"ok": False, "error": "Adresu se nepodařilo najít."}, status=404)
    return JsonResponse({"ok": True, "data": location})


@login_required
def address_reverse_geocode(request):
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
