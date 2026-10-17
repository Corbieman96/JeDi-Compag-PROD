from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.forms import AppSettingsForm
from core.models import AppSettings
from customer_requests.models import NoServiceCalendarDay
from waste_docs.services.operating_calendar.forms import NoServiceCalendarDayFormSet
from core.services.dashboard_context import build_dashboard_page_context
from users.constants import ROLE_RIDIC
from users.decorators import settings_nav_required
from users.services.post_login import default_post_login_url
from users.services.roles import get_user_role_label
from users.services.nav_visibility import effective_show_dashboard_nav


@login_required
def dashboard(request):
    """Úvodní přehled: řidiči, vozidla, dostupnost, průvodky (jízdy) podle dne, poznámky."""
    if get_user_role_label(request.user) == ROLE_RIDIC:
        return redirect("driver_portal:day_list")
    if not effective_show_dashboard_nav(request.user):
        return redirect(default_post_login_url(request.user))
    context = build_dashboard_page_context(request)
    return render(request, "core/dashboard.html", context)


@settings_nav_required
def app_settings(request):
    settings_obj = AppSettings.load()
    form = AppSettingsForm(request.POST or None, instance=settings_obj)
    formset = NoServiceCalendarDayFormSet(
        request.POST or None,
        queryset=NoServiceCalendarDay.objects.order_by("closed_date"),
        prefix="no_service",
    )
    if request.method == "POST":
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Nastavení bylo uloženo.")
            return redirect("core:settings")
        messages.error(request, "Dny bez svozu nebo nastavení se nepodařilo uložit.")
    return render(
        request,
        "core/settings.html",
        {"form": form, "no_service_formset": formset},
    )


@login_required
def help_page(request):
    return render(request, "core/help.html")


@login_required
@require_GET
def session_keepalive(request):
    """Lehký ping — SessionSecurityMiddleware obnoví auth_last_activity."""
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def session_close(request):
    """Beacon endpoint — prohlížeč volá při zavření záložky."""
    if request.user.is_authenticated:
        logout(request)
    return HttpResponse(status=204)
