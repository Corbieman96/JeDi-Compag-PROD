"""Session security: idle/lifetime limits and graceful session close."""

from __future__ import annotations

import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.exceptions import SessionInterrupted
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import resolve_url


SESSION_TOKEN_KEY = "auth_security_token"
SESSION_CREATED_AT_KEY = "auth_created_at"
SESSION_LAST_ACTIVITY_KEY = "auth_last_activity"
SESSION_EXPIRED_REASON = "idle"


def issue_security_session(request):
    now = int(time.time())
    request.session[SESSION_TOKEN_KEY] = secrets.token_urlsafe(32)
    request.session[SESSION_CREATED_AT_KEY] = now
    request.session[SESSION_LAST_ACTIVITY_KEY] = now


def effective_session_idle_seconds() -> int:
    """Idle timeout from AppSettings (minutes), fallback to Django settings."""
    fallback = int(getattr(settings, "SESSION_SECURITY_MAX_IDLE_SECONDS", 1800))
    try:
        from core.models import AppSettings

        minutes = int(AppSettings.load().session_idle_timeout_minutes or 0)
    except Exception:
        return fallback
    if minutes < 5:
        return fallback
    return min(minutes, 480) * 60


def login_url_for_session_expired(next_path: str, *, reason: str = SESSION_EXPIRED_REASON) -> str:
    """URL přihlášení s next= a reason= (pro hlášku na login stránce).

    LOGIN_URL může být jméno URL (např. \"login\") — musí projít resolve_url,
    jinak relativní Location \"login?...\" na /accounts/login/ dá 404 /accounts/login/login.
    """
    base = resolve_url(settings.LOGIN_URL or "/accounts/login/")
    parts = urlsplit(base)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["next"] = next_path or "/"
    query["reason"] = reason or SESSION_EXPIRED_REASON
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _is_ajax_request(request) -> bool:
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept.split(",")[0]


def _session_expired_response(request):
    if _is_ajax_request(request):
        return JsonResponse(
            {
                "ok": False,
                "error": "Přihlášení vypršelo. Obnovte stránku a přihlaste se.",
            },
            status=401,
        )
    return HttpResponseRedirect(
        login_url_for_session_expired(request.get_full_path())
    )


class SessionClosedMiddleware:
    """Gracefully handle SessionInterrupted (tab-close beacon race condition)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except SessionInterrupted:
            return _session_expired_response(request)


class SessionSecurityMiddleware:
    """Log out users when security token/limits are invalid."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            token = request.session.get(SESSION_TOKEN_KEY)
            created_at = int(request.session.get(SESSION_CREATED_AT_KEY, 0) or 0)
            last_activity = int(request.session.get(SESSION_LAST_ACTIVITY_KEY, 0) or 0)
            now = int(time.time())
            max_idle = effective_session_idle_seconds()
            max_lifetime = int(getattr(settings, "SESSION_SECURITY_MAX_LIFETIME_SECONDS", 28800))

            token_missing = not token
            idle_exceeded = last_activity and (now - last_activity > max_idle)
            lifetime_exceeded = created_at and (now - created_at > max_lifetime)

            if token_missing:
                # Stará relace před zavedením tokenu nebo soupeření o session – doplnit místo okamžitého odhlášení.
                issue_security_session(request)
            elif idle_exceeded or lifetime_exceeded:
                try:
                    from waste_docs.services.svoz_matrix_submit_error_log import (
                        record_yard_session_expired,
                    )

                    record_yard_session_expired(
                        user=request.user,
                        reason="lifetime" if lifetime_exceeded and not idle_exceeded else "idle",
                    )
                except Exception:
                    pass
                logout(request)
                return _session_expired_response(request)
            else:
                # Throttle: nechat session dirty jen jednou za ~60 s (méně zápisů do SQLite).
                if not last_activity or (now - last_activity) >= 60:
                    request.session[SESSION_LAST_ACTIVITY_KEY] = now

        return self.get_response(request)
