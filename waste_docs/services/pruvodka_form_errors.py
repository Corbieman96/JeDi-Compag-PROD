"""Souhrn chyb formuláře průvodky pro uživatele."""

from __future__ import annotations

from django.contrib import messages


def summarize_pruvodka_form_errors(form, *, max_items: int = 5) -> list[str]:
    lines: list[str] = []
    for field_name, field_errors in form.errors.items():
        if field_name == "__all__":
            for err in field_errors:
                lines.append(str(err))
            continue
        field = form.fields.get(field_name)
        label = getattr(field, "label", None) or field_name
        for err in field_errors:
            lines.append(f"{label}: {err}")
        if len(lines) >= max_items:
            break
    return lines[:max_items]


def flash_pruvodka_form_invalid(request, form) -> None:
    """Zobrazí uživateli důvod, proč se jízda neuložila."""
    messages.error(
        request,
        "Jízdu se nepodařilo uložit. Opravte zvýrazněná pole níže.",
    )
    for line in summarize_pruvodka_form_errors(form):
        messages.error(request, line)
