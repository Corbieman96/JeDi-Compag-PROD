"""POST endpoint hromadné výměny řidiče / RZ ze skupiny jízd."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from waste_docs.forms.ride_reassign_driver import RideReassignDriverForm
from waste_docs.services.ride_reassign_driver.apply import apply_ride_reassign_driver


@login_required
@require_POST
def ride_reassign_driver(request):
    form = RideReassignDriverForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Neplatný formulář výměny řidiče.")
        date_raw = (request.POST.get("drive_date") or "").strip()
        if date_raw:
            return redirect(f"{reverse('core:dashboard')}?date={date_raw}")
        return redirect("core:dashboard")

    result = apply_ride_reassign_driver(
        user=request.user,
        drive_date=form.cleaned_data["drive_date"],
        from_vehicle_rz_id=form.cleaned_data["from_vehicle_rz_id"],
        from_driver_id=form.cleaned_data["from_driver_id"],
        selected_pks=form.selected_ride_pks(),
        new_driver_id=int(form.cleaned_data["new_driver_id"]),
        new_vehicle_rz_id=form.cleaned_data.get("new_vehicle_rz_id"),
    )
    if result.ok:
        messages.success(request, result.message)
        return redirect(result.redirect_url or "core:dashboard")

    messages.error(request, result.message)
    date_iso = form.cleaned_data["drive_date"].isoformat()
    from_rz = form.cleaned_data["from_vehicle_rz_id"] or 0
    from_drv = form.cleaned_data["from_driver_id"] or 0
    group_key = f"{date_iso}::{int(from_rz)}::{int(from_drv)}"
    return redirect(f"{reverse('core:dashboard')}?date={date_iso}&ride_group={group_key}")
