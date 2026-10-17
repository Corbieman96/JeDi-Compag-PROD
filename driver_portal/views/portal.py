from datetime import date

from django.contrib import messages
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from users.constants import ROLE_RIDIC
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label

from driver_portal.forms import DriverRideUpdateForm
from driver_portal.services.rides import pruvodky_queryset_for_driver_day
from waste_docs.models import Pruvodka


def _require_ridic_role(request):
    if get_user_role_label(request.user) != ROLE_RIDIC:
        raise Http404()


def access_gate(request):
    """Veřejná stránka místo /login/ při vstupu na chráněný portál bez relace."""
    return render(request, "driver_portal/access_gate.html", {})


@require_http_methods(["POST"])
def driver_portal_logout(request):
    auth_logout(request)
    return redirect("driver_portal:gate")


@login_required(login_url="driver_portal:gate")
def day_list(request):
    _require_ridic_role(request)
    prof = get_access_profile(request.user)
    driver = prof.driver_profile
    if not driver:
        return render(request, "driver_portal/pairing_required.html", {})
    raw_date = (request.GET.get("date") or "").strip()
    try:
        day = date.fromisoformat(raw_date) if raw_date else timezone.localdate()
    except ValueError:
        day = timezone.localdate()
    rides = pruvodky_queryset_for_driver_day(driver.pk, day)
    return render(
        request,
        "driver_portal/day_list.html",
        {"driver": driver, "day": day, "rides": rides},
    )


@login_required(login_url="driver_portal:gate")
def ride_detail(request, pk: int):
    _require_ridic_role(request)
    prof = get_access_profile(request.user)
    driver = prof.driver_profile
    if not driver:
        return redirect("driver_portal:day_list")
    ride = get_object_or_404(
        Pruvodka.objects.filter(driver_id=driver.pk, is_archived=False),
        pk=pk,
    )
    if request.method == "POST":
        form = DriverRideUpdateForm(request.POST, instance=ride)
        if form.is_valid():
            form.save()
            messages.success(request, "Údaje byly uloženy.")
            return redirect("driver_portal:ride_detail", pk=ride.pk)
    else:
        form = DriverRideUpdateForm(instance=ride)
    return render(
        request,
        "driver_portal/ride_detail.html",
        {"ride": ride, "form": form, "driver": driver},
    )
