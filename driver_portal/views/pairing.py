from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from users.constants import ROLE_RIDIC
from users.models import UserAccessProfile
from users.services.access_profile import get_access_profile
from users.services.roles import get_user_role_label

from driver_portal.models import DriverPortalPairingToken
from driver_portal.services.display_code import normalize_display_code
from driver_portal.services.pairing_link_cookie import (
    clear_pairing_link_cookie,
    set_pairing_link_cookie,
    try_user_from_pairing_link_cookie,
)
from driver_portal.services.portal_driver_user import get_or_attach_user_for_driver_portal


def _conflict_other_user_has_driver(request, token):
    other = (
        UserAccessProfile.objects.filter(driver_profile_id=token.driver_id)
        .exclude(user_id=request.user.pk)
        .select_related("user")
        .first()
    )
    if other:
        return render(
            request,
            "driver_portal/pairing_invalid.html",
            {
                "reason": "driver_taken",
                "other_username": other.user.username,
                "token": token,
            },
            status=409,
        )
    return None


def _complete_pairing(request, token):
    if get_user_role_label(request.user) != ROLE_RIDIC:
        messages.error(request, "Propojení přes QR je určeno účtům s rolí „Řidič“.")
        return render(
            request,
            "driver_portal/pairing_invalid.html",
            {"reason": "role", "token": token},
            status=403,
        )

    resp = _conflict_other_user_has_driver(request, token)
    if resp is not None:
        return resp

    prof = get_access_profile(request.user)
    if prof.driver_profile_id and prof.driver_profile_id != token.driver_id:
        linked_driver = prof.driver_profile
        return render(
            request,
            "driver_portal/pairing_invalid.html",
            {
                "reason": "already_other_driver",
                "token": token,
                "linked_driver": linked_driver,
            },
            status=409,
        )

    if prof.driver_profile_id == token.driver_id:
        messages.info(request, "Účet je již propojen s touto pozvánkou.")
        resp = redirect("driver_portal:day_list")
        set_pairing_link_cookie(resp, request, request.user, token)
        return resp

    prof.driver_profile_id = token.driver_id
    prof.save(update_fields=["driver_profile_id"])
    messages.success(
        request,
        "Účet byl propojen s řidičským profilem. Nyní uvidíte své jízdy v portálu.",
    )
    resp = redirect("driver_portal:day_list")
    set_pairing_link_cookie(resp, request, request.user, token)
    return resp


@require_http_methods(["GET", "POST"])
def pair_by_token(request, secret: str):
    try:
        token = DriverPortalPairingToken.objects.select_related("driver").get(secret=secret)
    except DriverPortalPairingToken.DoesNotExist:
        return render(request, "driver_portal/pairing_invalid.html", {"reason": "missing"}, status=404)

    if token.status != DriverPortalPairingToken.Status.ACTIVE:
        return render(
            request,
            "driver_portal/pairing_invalid.html",
            {"reason": "inactive", "token": token},
            status=403,
        )

    if not request.user.is_authenticated:
        if request.method == "GET":
            cookie_user = try_user_from_pairing_link_cookie(request, token)
            if cookie_user is not None:
                auth_login(request, cookie_user)
                resp = redirect("driver_portal:day_list")
                set_pairing_link_cookie(resp, request, cookie_user, token)
                return resp
            return render(request, "driver_portal/pairing_login.html", {"token": token})
        entered_code = normalize_display_code(request.POST.get("display_code", ""))
        expected_code = normalize_display_code(token.display_code)
        if entered_code != expected_code:
            return render(
                request,
                "driver_portal/pairing_login.html",
                {"token": token, "code_error": True},
            )
        user = get_or_attach_user_for_driver_portal(token.driver)
        if get_user_role_label(user) != ROLE_RIDIC:
            return render(
                request,
                "driver_portal/pairing_login.html",
                {"token": token, "role_error": True},
            )
        auth_login(request, user)
        return _complete_pairing(request, token)

    if request.method == "POST":
        return _complete_pairing(request, token)

    prof = get_access_profile(request.user)
    if get_user_role_label(request.user) != ROLE_RIDIC:
        messages.error(request, "Propojení přes QR je určeno účtům s rolí „Řidič“.")
        return render(request, "driver_portal/pairing_invalid.html", {"reason": "role", "token": token}, status=403)

    resp = _conflict_other_user_has_driver(request, token)
    if resp is not None:
        return resp

    if prof.driver_profile_id and prof.driver_profile_id != token.driver_id:
        linked_driver = prof.driver_profile
        return render(
            request,
            "driver_portal/pairing_invalid.html",
            {
                "reason": "already_other_driver",
                "token": token,
                "linked_driver": linked_driver,
            },
            status=409,
        )

    already = prof.driver_profile_id == token.driver_id
    resp = render(
        request,
        "driver_portal/pairing_confirm.html",
        {"token": token, "already_linked": already},
    )
    if already:
        set_pairing_link_cookie(resp, request, request.user, token)
    return resp


@require_http_methods(["POST"])
def pairing_logout_and_retry(request, secret: str):
    """Odhlásí aktuální účet, smaže cookie pro rychlé přihlášení a vrátí na stejný odkaz z QR."""
    if not DriverPortalPairingToken.objects.filter(secret=secret).exists():
        return render(request, "driver_portal/pairing_invalid.html", {"reason": "missing"}, status=404)
    auth_logout(request)
    resp = redirect("driver_portal:pair", secret=secret)
    clear_pairing_link_cookie(resp, request)
    return resp
