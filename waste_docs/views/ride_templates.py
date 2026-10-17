from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalogs.catalog_nav_registry import SLUG_RIDE_TEMPLATES
from catalogs.models import ActivityCatalog, NameSubjectProfile
from users.services.access import can_see_all_waste_docs
from users.services.catalog_row_visibility import effective_show_catalog_index_row
from users.services.waste_doc_permissions import can_edit_existing_pruvodka
from waste_docs.forms import RideTemplateForm
from waste_docs.models import Pruvodka
from waste_docs.services.ride_templates import (
    create_ride_template_from_pruvodka,
    filter_ride_templates_by_vehicle_kind_ids,
    ride_templates_visible_queryset,
)


def ride_templates_access_required(view):
    return user_passes_test(
        lambda u: u.is_authenticated and effective_show_catalog_index_row(u, SLUG_RIDE_TEMPLATES)
    )(view)


def _vehicle_kind_ids_from_request(request) -> tuple[list[int], str | None]:
    raw = (request.GET.get("vehicle_kind_ids") or "").strip()
    if raw:
        out: list[int] = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except ValueError:
                return [], "Neplatný seznam druhů vozidla."
        return out, None
    vk_raw = (request.GET.get("vehicle_kind_id") or "").strip()
    if vk_raw:
        try:
            return [int(vk_raw)], None
        except ValueError:
            return [], "Neplatný druh vozidla."
    return [], None


@login_required
@require_POST
@ride_templates_access_required
def ride_template_create_from_pruvodka(request, pk):
    item = get_object_or_404(
        Pruvodka.objects.select_related(
            "activity",
            "driver",
            "vehicle_rz",
            "vehicle_rz__profile",
        ),
        pk=pk,
        is_archived=False,
    )
    if not can_see_all_waste_docs(request.user) and item.created_by_id != request.user.id:
        raise Http404("Jízda neexistuje.")
    if not can_edit_existing_pruvodka(request.user, item):
        raise Http404("Jízda neexistuje.")
    title = (request.POST.get("template_title") or "").strip()
    if not title:
        messages.error(request, "Zadejte název šablony.")
        return redirect("waste_docs:detail", pk=item.pk)
    raw_kind_ids = request.POST.getlist("template_vehicle_kind")
    kind_ids: list[int] = []
    for x in raw_kind_ids:
        try:
            kind_ids.append(int(x))
        except (TypeError, ValueError):
            messages.error(request, "Neplatný výběr druhů vozidla.")
            return redirect("waste_docs:detail", pk=item.pk)
    if not kind_ids:
        messages.error(request, "Vyberte alespoň jeden druh vozidla pro šablonu.")
        return redirect("waste_docs:detail", pk=item.pk)
    try:
        tpl = create_ride_template_from_pruvodka(
            item=item,
            created_by=request.user,
            title=title,
            vehicle_kind_ids=kind_ids,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("waste_docs:detail", pk=item.pk)
    messages.success(request, f"Šablona jízdy byla vytvořena: {tpl.title}.")
    return redirect("waste_docs:detail", pk=item.pk)


@login_required
@ride_templates_access_required
def ride_templates_by_vehicle_kind(request):
    kind_ids, err = _vehicle_kind_ids_from_request(request)
    if err:
        return JsonResponse({"ok": False, "error": err}, status=400)
    activity_raw = (request.GET.get("activity_id") or "").strip()
    rows_qs = ride_templates_visible_queryset(request.user)
    activity_id = None
    if activity_raw:
        try:
            activity_id = int(activity_raw)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Neplatná činnost."}, status=400)
    if kind_ids:
        rows_qs = filter_ride_templates_by_vehicle_kind_ids(rows_qs, kind_ids)
    elif activity_id:
        act_kind_ids = list(
            ActivityCatalog.objects.filter(pk=activity_id).values_list("vehicle_kinds__id", flat=True)
        )
        act_kind_ids = [kid for kid in act_kind_ids if kid]
        if not act_kind_ids:
            return JsonResponse({"ok": True, "data": []})
        rows_qs = filter_ride_templates_by_vehicle_kind_ids(rows_qs, act_kind_ids)
    else:
        return JsonResponse({"ok": True, "data": []})
    rows = (
        rows_qs.select_related("activity", "name", "ico", "address", "waste_type", "suffix", "vehicle_rz", "driver")
        .prefetch_related("applicable_vehicle_kinds")
        .order_by("title", "-updated_at")
        .distinct()
    )
    name_ids = [row.name_id for row in rows]
    subject_map = {
        row.name_id: row
        for row in NameSubjectProfile.objects.filter(name_id__in=name_ids).select_related(
            "address_profile__facility_address"
        )
    }
    data = []
    for row in rows:
        subject = subject_map.get(row.name_id)
        facility_address_value = ""
        if subject and subject.facility_address:
            facility_address_value = subject.facility_address.value
        data.append(
            {
                "id": row.pk,
                "title": row.title,
                "activity_id": row.activity_id,
                "name_id": row.name_id,
                "name_value": row.name.value,
                "ico_id": row.ico_id,
                "ico_value": row.ico.value,
                "address_value": row.address.value,
                "facility_address_value": facility_address_value,
                "waste_type_id": row.waste_type_id,
                "suffix_id": row.suffix_id,
                "vehicle_rz_id": row.vehicle_rz_id,
                "vehicle_rz_label": row.vehicle_rz.value if row.vehicle_rz_id else "",
                "driver_id": row.driver_id,
                "driver_label": str(row.driver) if row.driver_id else "",
                "container_number": row.container_number or "",
                "container_number_2": row.container_number_2 or "",
                "contact_phone": row.contact_phone or "",
                "contract_number": row.contract_number or "",
                "contact_note": row.contact_note or "",
            }
        )
    return JsonResponse({"ok": True, "data": data})


@login_required
@ride_templates_access_required
def ride_template_list(request):
    items = (
        ride_templates_visible_queryset(request.user)
        .select_related("vehicle_kind", "activity", "name", "vehicle_rz", "driver")
        .prefetch_related("applicable_vehicle_kinds")
        .order_by("title", "-updated_at")
    )
    return render(request, "waste_docs/ride_template_list.html", {"items": items})


@login_required
@ride_templates_access_required
def ride_template_edit(request, pk):
    item = get_object_or_404(ride_templates_visible_queryset(request.user), pk=pk)
    form = RideTemplateForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Šablona byla upravena.")
        return redirect("waste_docs:ride_template_list")
    return render(
        request,
        "waste_docs/ride_template_form.html",
        {"form": form, "item": item, "is_edit": True},
    )


@login_required
@ride_templates_access_required
def ride_template_delete(request, pk):
    item = get_object_or_404(ride_templates_visible_queryset(request.user), pk=pk)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Šablona byla smazána.")
        return redirect("waste_docs:ride_template_list")
    return render(request, "waste_docs/ride_template_confirm_delete.html", {"item": item})
