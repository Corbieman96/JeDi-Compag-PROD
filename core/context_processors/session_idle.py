"""Idle session timeout pro globální JS watchdog."""

from __future__ import annotations

from django.conf import settings
from django.urls import reverse

from core.security import effective_session_idle_seconds


def session_idle_watch(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {
            "session_idle_watch_enabled": False,
            "session_idle_timeout_ms": 0,
            "session_login_url": "",
            "session_keepalive_url": "",
        }
    try:
        idle_ms = int(effective_session_idle_seconds()) * 1000
    except Exception:
        idle_ms = int(getattr(settings, "SESSION_SECURITY_MAX_IDLE_SECONDS", 1800)) * 1000
    return {
        "session_idle_watch_enabled": True,
        "session_idle_timeout_ms": idle_ms,
        "session_login_url": reverse(settings.LOGIN_URL),
        "session_keepalive_url": reverse("core:session_keepalive"),
    }
