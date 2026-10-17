from django.contrib.auth.decorators import user_passes_test
from django.forms import modelform_factory
from django.http import Http404

from users.decorators import catalogs_nav_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalogs.catalog_definitions import CATALOGS, HIDDEN_CATALOG_SLUGS
from catalogs.catalog_nav_registry import SLUG_OFFLINE_ADDRESSES, visible_catalog_index_sections


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


def _get_catalog(slug):
    try:
        return CATALOGS[slug]
    except KeyError as exc:
        raise Http404("Číselník neexistuje.") from exc


@catalogs_nav_required
def catalog_index(request):
    catalog_sections = visible_catalog_index_sections(request.user)
    show_offline_address_row = any(
        row["slug"] == SLUG_OFFLINE_ADDRESSES
        for section in catalog_sections
        for row in section["rows"]
    )
    address_data_create_url = (
        reverse("address_data:create") if show_offline_address_row else ""
    )
    return render(
        request,
        "catalogs/index.html",
        {
            "catalog_sections": catalog_sections,
            "address_data_create_url": address_data_create_url,
        },
    )


@admin_required
def catalog_list(request, slug):
    if slug == "name":
        return redirect("catalogs:name_list")
    if slug == "suffix":
        return redirect("catalogs:suffix_list")
    if slug == "waste-type":
        return redirect("catalogs:waste_type_list")
    if slug == "vehicle-rz":
        return redirect("catalogs:vehicle_rz_list")
    if slug == "activity":
        return redirect("catalogs:activity_list")
    if slug == "drivers":
        return redirect("catalogs:driver_list")
    if slug in HIDDEN_CATALOG_SLUGS:
        raise Http404("Číselník není dostupný.")
    label, model = _get_catalog(slug)
    items = model.objects.all()
    return render(
        request,
        "catalogs/catalog_list.html",
        {"items": items, "slug": slug, "label": label},
    )


@admin_required
def catalog_edit(request, slug, pk):
    if slug == "name":
        return redirect("catalogs:name_edit", pk=pk)
    if slug == "suffix":
        return redirect("catalogs:suffix_edit", pk=pk)
    if slug == "waste-type":
        return redirect("catalogs:waste_type_edit", pk=pk)
    if slug == "vehicle-rz":
        return redirect("catalogs:vehicle_rz_edit", pk=pk)
    if slug == "activity":
        return redirect("catalogs:activity_edit", pk=pk)
    if slug == "drivers":
        return redirect("catalogs:driver_edit", pk=pk)
    if slug in HIDDEN_CATALOG_SLUGS:
        raise Http404("Číselník není dostupný.")
    label, model = _get_catalog(slug)
    item = get_object_or_404(model, pk=pk)
    form_cls = modelform_factory(model, fields=("value",))
    form = form_cls(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:list", slug=slug)
    return render(
        request,
        "catalogs/catalog_form.html",
        {"form": form, "label": label, "slug": slug, "is_edit": True, "item": item},
    )


@admin_required
def catalog_create(request, slug):
    if slug == "name":
        return redirect("catalogs:name_create")
    if slug == "suffix":
        return redirect("catalogs:suffix_create")
    if slug == "waste-type":
        return redirect("catalogs:waste_type_create")
    if slug == "vehicle-rz":
        return redirect("catalogs:vehicle_rz_create")
    if slug == "activity":
        return redirect("catalogs:activity_create")
    if slug == "drivers":
        return redirect("catalogs:driver_create")
    if slug in HIDDEN_CATALOG_SLUGS:
        raise Http404("Číselník není dostupný.")
    label, model = _get_catalog(slug)
    form_cls = modelform_factory(model, fields=("value",))
    form = form_cls(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:list", slug=slug)
    return render(
        request,
        "catalogs/catalog_form.html",
        {"form": form, "label": label, "slug": slug, "is_edit": False},
    )


@admin_required
def catalog_delete(request, slug, pk):
    if slug == "name":
        return redirect("catalogs:name_list")
    if slug == "suffix":
        return redirect("catalogs:suffix_list")
    if slug == "waste-type":
        return redirect("catalogs:waste_type_list")
    if slug == "vehicle-rz":
        return redirect("catalogs:vehicle_rz_list")
    if slug == "activity":
        return redirect("catalogs:activity_list")
    if slug == "drivers":
        return redirect("catalogs:driver_list")
    if slug in HIDDEN_CATALOG_SLUGS:
        raise Http404("Číselník není dostupný.")
    label, model = _get_catalog(slug)
    item = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:list", slug=slug)
    return render(
        request,
        "catalogs/catalog_confirm_delete.html",
        {"item": item, "label": label, "slug": slug},
    )
