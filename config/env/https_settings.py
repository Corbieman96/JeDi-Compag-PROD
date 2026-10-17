"""Bezpečnostní přepínače pro provoz přes HTTPS (cookie flags, CSRF origins)."""

from __future__ import annotations

from typing import Any

from config.env.project_env import ProjectEnv


def extra_django_settings(env: ProjectEnv) -> dict[str, Any]:
    if not env.use_https:
        return {}
    data: dict[str, Any] = {
        "SESSION_COOKIE_SECURE": True,
        "CSRF_COOKIE_SECURE": True,
    }
    if env.secure_ssl_redirect:
        data["SECURE_SSL_REDIRECT"] = True
    if env.csrf_trusted_origins:
        data["CSRF_TRUSTED_ORIGINS"] = env.csrf_trusted_origins
    return data
