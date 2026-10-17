from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from catalogs.forms import WasteTypeCatalogForm
from catalogs.models import WasteTypeCatalog
from catalogs.services import import_waste_types_from_xlsx
from catalogs.waste_catalog_code import normalize_waste_catalog_code


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


@admin_required
def waste_type_list(request):
    query = (request.GET.get("q") or "").strip()
    items = WasteTypeCatalog.objects.all()

    normalized_query = normalize_waste_catalog_code(query) if query else ""
    query_compact = (
        normalized_query.replace(" ", "").replace("*", "")
        if normalized_query
        else query.replace(" ", "").replace("*", "")
    )
    items_out = []
    for row in items:
        code_disp = normalize_waste_catalog_code(row.code) or ""
        if not code_disp:
            continue
        if query:
            value_text = (row.value or "").strip().lower()
            query_text = query.lower()
            code_compact = code_disp.replace(" ", "").replace("*", "")
            # Vyhledávání: přesná normalizace kódu i fulltext v názvu.
            if (
                query_text not in value_text
                and query_text not in code_disp.lower()
                and (not query_compact or query_compact not in code_compact)
            ):
                continue
        row.code_display = code_disp
        row.value_display = (row.value or "").strip()
        items_out.append(row)

    return render(
        request,
        "catalogs/waste_type_list.html",
        {
            "items": items_out,
            "q": query,
            "results_count": len(items_out),
        },
    )


@admin_required
def waste_type_create(request):
    form = WasteTypeCatalogForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:waste_type_list")
    return render(request, "catalogs/waste_type_form.html", {"form": form, "is_edit": False})


@admin_required
def waste_type_edit(request, pk):
    item = get_object_or_404(WasteTypeCatalog, pk=pk)
    form = WasteTypeCatalogForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:waste_type_list")
    return render(request, "catalogs/waste_type_form.html", {"form": form, "is_edit": True, "item": item})


@admin_required
def waste_type_delete(request, pk):
    item = get_object_or_404(WasteTypeCatalog, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:waste_type_list")
    item.code_display = normalize_waste_catalog_code(item.code) or ""
    item.value_display = (item.value or "").strip()
    return render(request, "catalogs/waste_type_confirm_delete.html", {"item": item})


@admin_required
def waste_type_import(request):
    file_path = settings.BASE_DIR / "Katalog-odpadu-2025.xlsx"
    if not Path(file_path).exists():
        messages.error(request, "Soubor Katalog-odpadu-2025.xlsx nebyl nalezen v kořeni projektu.")
        return redirect("catalogs:waste_type_list")
    result = import_waste_types_from_xlsx(path=file_path)
    messages.success(
        request,
        f"Import hotov: vytvořeno {result.created}, upraveno {result.updated}, přeskočeno {result.skipped}.",
    )
    return redirect("catalogs:waste_type_list")
