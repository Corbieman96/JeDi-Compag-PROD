from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from catalogs.forms.activity import ActivityCatalogForm, ActivityFieldRuleFormSet
from catalogs.models import ActivityCatalog
from waste_docs.activity_fields import apply_mobile_container_slot_choice


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


@admin_required
def activity_list(request):
    items = ActivityCatalog.objects.prefetch_related("vehicle_kinds", "follow_up_activities").order_by("name")
    return render(request, "catalogs/activity_list.html", {"items": items})


@admin_required
def activity_create(request):
    if request.method == "POST":
        form = ActivityCatalogForm(request.POST)
        if form.is_valid():
            item = form.save()
            formset = ActivityFieldRuleFormSet(request.POST, instance=item)
            if formset.is_valid():
                formset.save()
                apply_mobile_container_slot_choice(item, form.cleaned_data["mobile_container_slots"])
                return redirect("catalogs:activity_list")
            item.delete()
        else:
            formset = ActivityFieldRuleFormSet(request.POST, instance=ActivityCatalog())
    else:
        form = ActivityCatalogForm()
        formset = ActivityFieldRuleFormSet(instance=ActivityCatalog())
    return render(
        request,
        "catalogs/activity_form.html",
        {"form": form, "formset": formset, "is_edit": False},
    )


@admin_required
def activity_edit(request, pk):
    item = get_object_or_404(ActivityCatalog, pk=pk)
    if request.method == "POST":
        form = ActivityCatalogForm(request.POST, instance=item)
        formset = ActivityFieldRuleFormSet(request.POST, instance=item)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            apply_mobile_container_slot_choice(item, form.cleaned_data["mobile_container_slots"])
            return redirect("catalogs:activity_list")
    else:
        form = ActivityCatalogForm(instance=item)
        formset = ActivityFieldRuleFormSet(instance=item)
    return render(
        request,
        "catalogs/activity_form.html",
        {"form": form, "formset": formset, "is_edit": True, "item": item},
    )


@admin_required
def activity_delete(request, pk):
    item = get_object_or_404(ActivityCatalog, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:activity_list")
    return render(request, "catalogs/activity_confirm_delete.html", {"item": item})
