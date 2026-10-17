"""Django system checks pro strukturu projektu."""

from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.checks import Error, Tags, register

from core.module_package_guard import RISKY_MODULE_NAMES, find_conflicts_in_app_directory

_CHECK_ID = "core.E001"


@register(Tags.compatibility)
def check_no_module_package_name_twins(app_configs, **kwargs):
    """
    U vlastních aplikací pod BASE_DIR zakážeme současně `foo.py` i balíček `foo/`
    pro typické moduly (models, forms, …).
    """
    errors = []
    if app_configs is None:
        app_configs = tuple(apps.get_app_configs())
    base = Path(settings.BASE_DIR).resolve()
    for app in app_configs:
        app_path = Path(app.path).resolve()
        try:
            app_path.relative_to(base)
        except ValueError:
            continue
        for stem, mod, pkg in find_conflicts_in_app_directory(app_path):
            risk = stem in RISKY_MODULE_NAMES
            hint = (
                f"Nechte jen balíček `{stem}/` (s __init__.py) a smažte nebo přejmenujte `{stem}.py`, "
                "nebo naopak — Python/importy pak závisí na pořadí a IDE může ukazovat špatný soubor."
            )
            if risk:
                hint = f"U modulu `{stem}` jde o typický konflikt po rozdělení do podsložky. {hint}"
            errors.append(
                Error(
                    f"Kolize názvu v aplikaci '{app.label}': existuje `{stem}.py` i balíček `{stem}/`.",
                    hint=hint,
                    obj=str(mod),
                    id=_CHECK_ID,
                )
            )
    return errors
