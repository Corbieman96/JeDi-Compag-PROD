"""CRUD středisek pasportů kontejnerů."""

from __future__ import annotations

from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from catalogs.catalog_nav_registry import SLUG_CONTAINER_PASSPORT
from catalogs.forms.pasport_stredisko import PasportStrediskoForm
from catalogs.models import PasportStredisko
from users.decorators import catalogs_nav_required
from users.services.catalog_row_visibility import effective_show_catalog_index_row


def _require_container_passport_catalog_visible(user):
    return user.is_authenticated and effective_show_catalog_index_row(user, SLUG_CONTAINER_PASSPORT)


admin_required = user_passes_test(lambda u: u.is_authenticated and u.is_superuser)


@catalogs_nav_required
@admin_required
def pasport_stredisko_list(request):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    items = PasportStredisko.objects.all().order_by("sort_order", "code", "pk")
    return render(request, "catalogs/pasport_stredisko_list.html", {"items": items})


@catalogs_nav_required
@admin_required
def pasport_stredisko_create(request):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    form = PasportStrediskoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:pasport_stredisko_list")
    return render(request, "catalogs/pasport_stredisko_form.html", {"form": form, "is_edit": False})


@catalogs_nav_required
@admin_required
def pasport_stredisko_edit(request, pk):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    item = get_object_or_404(PasportStredisko, pk=pk)
    form = PasportStrediskoForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:pasport_stredisko_list")
    return render(request, "catalogs/pasport_stredisko_form.html", {"form": form, "is_edit": True, "item": item})


@catalogs_nav_required
@admin_required
def pasport_stredisko_delete(request, pk):
    if not _require_container_passport_catalog_visible(request.user):
        raise Http404()
    item = get_object_or_404(PasportStredisko, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:pasport_stredisko_list")
    return render(request, "catalogs/pasport_stredisko_confirm_delete.html", {"item": item})
