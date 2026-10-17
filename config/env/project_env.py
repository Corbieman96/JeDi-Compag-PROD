from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.env.parsing import env_bool, env_csv

_DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = (
    "127.0.0.1",
    "localhost",
    "192.168.68.51",
    "192.168.68.60",
    "192.168.68.61",
    "192.168.68.62",
    "192.168.68.63",
    "192.168.1.18",
    "192.168.1.152",
    "192.168.1.162",
    "192.168.1.215",
    "192.168.1.225",
    "192.168.1.123",
)


@dataclass(frozen=True)
class ProjectEnv:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    jedis_version: str
    environment: str
    serve_media: bool
    use_https: bool
    csrf_trusted_origins: list[str]
    secure_ssl_redirect: bool

    @classmethod
    def from_base_dir(cls, base_dir: Path) -> ProjectEnv:
        debug = env_bool("DEBUG", default=True)
        secret_key = (os.environ.get("SECRET_KEY") or "").strip()
        if not secret_key:
            raise ImproperlyConfigured(
                "Nastavte neprázdnou proměnnou SECRET_KEY v souboru .env v kořeni projektu "
                "(nebo v systémovém prostředí)."
            )

        allowed_hosts = env_csv("ALLOWED_HOSTS", default=_DEFAULT_ALLOWED_HOSTS)
        jedis_version = (os.environ.get("JEDIS_VERSION") or "5.0.0").strip()
        environment = (os.environ.get("JEDIS_ENVIRONMENT") or "PROD").strip().upper()
        serve_media = env_bool("SERVE_MEDIA", default=debug)
        use_https = env_bool("USE_HTTPS", default=False)
        csrf_trusted_origins = env_csv("CSRF_TRUSTED_ORIGINS")
        secure_ssl_redirect = env_bool("SECURE_SSL_REDIRECT", default=False)

        return cls(
            secret_key=secret_key,
            debug=debug,
            allowed_hosts=allowed_hosts,
            jedis_version=jedis_version,
            environment=environment,
            serve_media=serve_media,
            use_https=use_https,
            csrf_trusted_origins=csrf_trusted_origins,
            secure_ssl_redirect=secure_ssl_redirect,
        )
