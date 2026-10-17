from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalogs.forms import DriverAbsenceForm, DriverAbsenceQuickForm, DriverProfileForm
from catalogs.models import DriverAbsence, DriverProfile
from catalogs.services.driver_absence_display import build_driver_absence_display_rows
from catalogs.services.driver_absence_profile_summary import (
    absence_total_count_for_driver,
    absence_years_for_driver,
    active_absence_on_date,
)
from catalogs.services.driver_list_filters import (
    driver_vehicle_kind_options,
    filter_driver_list_queryset,
    parse_driver_list_filter_request,
)
from driver_portal.models import DriverPortalPairingToken
from users.models import UserAccessProfile
from driver_portal.services.pairing_link import absolute_pairing_url_secret, pairing_url_is_relative, qr_png_data_uri
from driver_portal.services.token_admin import create_token_for_driver, set_token_status_for_driver
from users.services.access import can_manage_driver_absences
from users.services.catalog_row_visibility import effective_show_catalog_index_row


def admin_required(view):
    return user_passes_test(lambda u: u.is_authenticated and u.is_superuser)(view)


def _require_drivers_catalog_visible(user):
    """Přístup k /catalogs/drivers/ podle řádku „Řidiči“ v profilu uživatele (catnav)."""
    return bool(user.is_authenticated and effective_show_catalog_index_row(user, "drivers"))


def drivers_catalog_visible(view):
    return user_passes_test(_require_drivers_catalog_visible)(view)


def driver_absence_manager_required(view):
    return user_passes_test(can_manage_driver_absences)(view)


def _portal_invite_rows(request, driver_pk: int):
    tokens = DriverPortalPairingToken.objects.filter(driver_id=driver_pk).order_by("-created_at")[:50]
    rows = []
    for t in tokens:
        url = absolute_pairing_url_secret(t.secret, request=request)
        rows.append(
            {
                "token": t,
                "pairing_url": url,
                "qr_data_uri": qr_png_data_uri(url),
                "needs_public_base": pairing_url_is_relative(url),
            }
        )
    return rows


@drivers_catalog_visible
def driver_list(request):
    state = parse_driver_list_filter_request(request)
    return render(
        request,
        "catalogs/driver_list.html",
        {
            "items": filter_driver_list_queryset(state),
            "filter_vehicle_kind_id": state.vehicle_kind_id,
            "has_filters": state.has_filters,
            "vehicle_kind_options": driver_vehicle_kind_options(),
        },
    )


@drivers_catalog_visible
def driver_create(request):
    form = DriverProfileForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:driver_list")
    return render(request, "catalogs/driver_form.html", {"form": form, "is_edit": False})


@drivers_catalog_visible
def driver_edit(request, pk):
    item = get_object_or_404(DriverProfile, pk=pk)
    form = DriverProfileForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("catalogs:driver_list")
    absences = list(item.absences.order_by("-date_from", "-date_to", "-pk")[:500])
    absence_total_count = absence_total_count_for_driver(item.pk)
    absence_years = absence_years_for_driver(item.pk)
    current_year = date.today().year
    absence_default_year = current_year if current_year in absence_years else ""
    today_absence = active_absence_on_date(item, date.today())
    invite_rows = _portal_invite_rows(request, item.pk)
    portal_linked_profile = (
        UserAccessProfile.objects.filter(driver_profile_id=item.pk)
        .select_related("user")
        .first()
    )
    return render(
        request,
        "catalogs/driver_form.html",
        {
            "form": form,
            "is_edit": True,
            "item": item,
            "absence_rows": build_driver_absence_display_rows(absences),
            "absence_total_count": absence_total_count,
            "absence_loaded_count": len(absences),
            "absence_years": absence_years,
            "absence_default_year": absence_default_year,
            "absence_type_choices": DriverAbsence.AbsenceType.choices,
            "absence_active_today_label": (
                today_absence.get_absence_type_display() if today_absence else ""
            ),
            "portal_invite_rows": invite_rows,
            "portal_linked_profile": portal_linked_profile,
        },
    )


@admin_required
@require_POST
def driver_portal_invite_create(request, pk):
    driver = get_object_or_404(DriverProfile, pk=pk)
    note = (request.POST.get("invite_note") or "").strip()
    create_token_for_driver(driver_id=driver.pk, note=note)
    messages.success(request, "Nová pozvánka (QR) byla vytvořena.")
    return redirect("catalogs:driver_edit", pk=driver.pk)


@admin_required
@require_POST
def driver_portal_unlink_linked_user(request, pk):
    """Zruší vazbu UserAccessProfile → tento řidič (uvolní QR párování pro jiný účet)."""
    driver = get_object_or_404(DriverProfile, pk=pk)
    qs = UserAccessProfile.objects.filter(driver_profile_id=driver.pk)
    count = qs.count()
    qs.update(driver_profile=None)
    if count:
        messages.success(
            request,
            "Propojení telefonu portálu u tohoto řidiče bylo zrušeno. Stejný QR teď může přiřadit jiný účet s rolí „Řidič“.",
        )
    else:
        messages.info(request, "U tohoto řidiče nebyl k portálu přiřazen žádný uživatelský účet.")
    return redirect("catalogs:driver_edit", pk=driver.pk)


@admin_required
@require_POST
def driver_portal_invite_set_status(request, pk, token_pk):
    driver = get_object_or_404(DriverProfile, pk=pk)
    status = (request.POST.get("status") or "").strip()
    try:
        set_token_status_for_driver(token_id=token_pk, driver_id=driver.pk, status=status)
    except Http404:
        messages.error(request, "Pozvánka u tohoto řidiče nebyla nalezena.")
    except ValueError:
        messages.error(request, "Neplatný stav pozvánky.")
    else:
        messages.success(request, "Stav pozvánky byl uložen.")
    return redirect("catalogs:driver_edit", pk=driver.pk)


@driver_absence_manager_required
@require_POST
def driver_absence_quick_add(request):
    form = DriverAbsenceQuickForm(request.POST)
    next_date = (request.POST.get("next_date") or "").strip()
    if form.is_valid():
        absence = form.save(commit=False)
        absence.created_by = request.user
        absence.save()
        messages.success(request, "Nepřítomnost byla uložena.")
    else:
        err = "; ".join(f"{k}: {', '.join(v)}" for k, v in form.errors.items())
        messages.error(
            request,
            f"Nepřítomnost se nepodařila uložit. {err}" if err else "Chyba formuláře.",
        )
    url = reverse("core:dashboard")
    if next_date:
        return redirect(f"{url}?date={next_date}")
    return redirect(url)


@driver_absence_manager_required
@require_POST
def driver_absence_quick_update(request, driver_pk, absence_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    absence = get_object_or_404(DriverAbsence, pk=absence_pk, driver_id=driver.pk)
    next_date = (request.POST.get("next_date") or "").strip()
    form = DriverAbsenceForm(request.POST, instance=absence)
    if form.is_valid():
        form.save()
        messages.success(request, "Nepřítomnost byla upravena.")
    else:
        err = "; ".join(f"{k}: {', '.join(v)}" for k, v in form.errors.items())
        messages.error(
            request,
            f"Nepřítomnost se nepodařila upravit. {err}" if err else "Chyba formuláře.",
        )
    url = reverse("core:dashboard")
    if next_date:
        return redirect(f"{url}?date={next_date}")
    return redirect(url)


@driver_absence_manager_required
@require_POST
def driver_absence_quick_delete(request, driver_pk, absence_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    absence = get_object_or_404(DriverAbsence, pk=absence_pk, driver_id=driver.pk)
    next_date = (request.POST.get("next_date") or "").strip()
    absence.delete()
    messages.success(request, "Nepřítomnost byla smazána.")
    url = reverse("core:dashboard")
    if next_date:
        return redirect(f"{url}?date={next_date}")
    return redirect(url)


@driver_absence_manager_required
@require_POST
def driver_availability_note_quick_clear(request, driver_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    next_date = (request.POST.get("next_date") or "").strip()
    driver.availability_note = ""
    driver.save(update_fields=["availability_note"])
    messages.success(request, "Poznámka nepřítomnosti byla zrušena.")
    url = reverse("core:dashboard")
    if next_date:
        return redirect(f"{url}?date={next_date}")
    return redirect(url)


@admin_required
@require_POST
def driver_availability_note_quick_update(request, driver_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    next_date = (request.POST.get("next_date") or "").strip()
    note = (request.POST.get("availability_note") or "").strip()
    driver.availability_note = note
    driver.save(update_fields=["availability_note"])
    messages.success(request, "Poznámka nepřítomnosti byla upravena.")
    url = reverse("core:dashboard")
    if next_date:
        return redirect(f"{url}?date={next_date}")
    return redirect(url)


@admin_required
def driver_absence_edit(request, driver_pk, absence_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    absence = get_object_or_404(DriverAbsence, pk=absence_pk, driver_id=driver.pk)
    form = DriverAbsenceForm(request.POST or None, instance=absence)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Nepřítomnost byla upravena.")
        return redirect("catalogs:driver_edit", pk=driver.pk)
    return render(
        request,
        "catalogs/driver_absence_form.html",
        {"form": form, "driver": driver, "absence": absence},
    )


@admin_required
def driver_absence_delete(request, driver_pk, absence_pk):
    driver = get_object_or_404(DriverProfile, pk=driver_pk)
    absence = get_object_or_404(DriverAbsence, pk=absence_pk, driver_id=driver.pk)
    if request.method == "POST":
        absence.delete()
        messages.success(request, "Nepřítomnost byla smazána.")
        return redirect("catalogs:driver_edit", pk=driver.pk)
    return render(
        request,
        "catalogs/driver_absence_confirm_delete.html",
        {"driver": driver, "absence": absence},
    )


@admin_required
def driver_delete(request, pk):
    item = get_object_or_404(DriverProfile, pk=pk)
    if request.method == "POST":
        item.delete()
        return redirect("catalogs:driver_list")
    return render(request, "catalogs/driver_confirm_delete.html", {"item": item})
