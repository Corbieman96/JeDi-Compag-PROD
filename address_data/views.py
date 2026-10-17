from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from users.decorators import address_data_nav_required

from catalogs.services.address import normalize_czech_address
from catalogs.services.geocoding import fetch_czech_addresses

from address_data.services.offline_persist import bulk_save_rows, upsert_offline_rows
from address_data.services.ruian_import import iter_region_addresses

from .forms import OfflineAddressForm
from .models import OfflineAddress


def _import_ruian_regions() -> tuple[int, list[tuple[str, int]]]:
    regions = list(getattr(settings, "OFFLINE_ADDRESS_RUIAN_REGIONS", []))
    max_per_region = int(getattr(settings, "OFFLINE_ADDRESS_RUIAN_MAX_PER_REGION", 600_000))
    max_per_region = max(1000, min(max_per_region, 1_000_000))
    known_keys = set(OfflineAddress.objects.values_list("city", "street", "house_number"))
    total_saved = 0
    per_region: list[tuple[str, int]] = []
    for region in regions:
        region_saved = 0
        batch: list[dict] = []
        for row in iter_region_addresses(region_name=region, max_rows=max_per_region):
            batch.append(row)
            if len(batch) >= 2000:
                saved, _ = bulk_save_rows(batch, known_keys=known_keys, batch_size=2000)
                region_saved += saved
                total_saved += saved
                batch.clear()
        if batch:
            saved, _ = bulk_save_rows(batch, known_keys=known_keys, batch_size=2000)
            region_saved += saved
            total_saved += saved
        per_region.append((region, region_saved))
    return total_saved, per_region


@address_data_nav_required
def address_list(request):
    q = (request.GET.get("q") or "").strip()
    city = (request.GET.get("city") or "").strip()
    street = (request.GET.get("street") or "").strip()
    house_number = (request.GET.get("house_number") or "").strip()
    if request.method == "GET" and not OfflineAddress.objects.exists():
        messages.info(
            request,
            "Databáze adres je prázdná — načtěte kraje tlačítkem níže nebo použijte "
            "příkaz: python manage.py import_ruian_regions --replace",
        )
    if request.method == "POST":
        if (request.POST.get("action") or "").strip() == "bootstrap_regions":
            total_saved, per_region = _import_ruian_regions()
            details = ", ".join(f"{name}: {count}" for name, count in per_region)
            if details:
                messages.success(
                    request,
                    f"Načteno z RÚIAN celkem {total_saved} adres ({details}).",
                )
            else:
                messages.success(request, f"Načteno z RÚIAN celkem {total_saved} adres.")
            return redirect("address_data:list")
        query = normalize_czech_address((request.POST.get("osm_query") or "").strip())
        try:
            limit = int((request.POST.get("osm_limit") or "1000").strip())
        except ValueError:
            limit = 1000
        limit = max(1, min(limit, 5000))
        if len(query) < 2:
            messages.error(request, "Zadejte alespoň 2 znaky pro načtení z OpenStreetMap.")
            return redirect("address_data:list")
        rows = fetch_czech_addresses(query=query, limit=limit)
        if not rows:
            messages.warning(request, "OpenStreetMap nevrátil žádné adresy.")
            return redirect("address_data:list")
        saved = upsert_offline_rows(rows)
        messages.success(request, f"Načteno z OpenStreetMap a uloženo adres: {saved}.")
        return redirect("address_data:list")

    items = OfflineAddress.objects.all()
    if q:
        items = items.filter(label__icontains=q)
    if city:
        items = items.filter(city__icontains=city)
    if street:
        items = items.filter(street__icontains=street)
    if house_number:
        items = items.filter(house_number__icontains=house_number)
    return render(
        request,
        "address_data/list.html",
        {
            "items": items[:200],
            "q": q,
            "city": city,
            "street": street,
            "house_number": house_number,
            "ruian_regions": list(getattr(settings, "OFFLINE_ADDRESS_RUIAN_REGIONS", [])),
        },
    )


@address_data_nav_required
def address_create(request):
    form = OfflineAddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("address_data:list")
    return render(request, "address_data/form.html", {"form": form})


@address_data_nav_required
def address_delete(request, pk):
    item = get_object_or_404(OfflineAddress, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("address_data:list")
    return render(request, "address_data/confirm_delete.html", {"item": item})
