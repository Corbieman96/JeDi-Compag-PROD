from django import forms

from core.models import AppSettings
from users.constants import ROLE_CHOICES
from users.services.nav_visibility import ROLE_NAV_FLAG_KEYS, ROLE_NAV_LABELS_CZ, merged_role_nav_matrix
from users.services.role_permissions import (
    ROLE_PERMISSION_FLAG_KEYS,
    ROLE_PERMISSION_LABELS_CZ,
    merged_role_permission_matrix,
)


class AppSettingsForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = (
            "default_map_lat",
            "default_map_lng",
            "waste_docs_default_range_days",
            "svoz_disable_yard_daily_submit_limit",
            "enforce_container_passport_move_check",
            "customer_request_daily_cutoff_time",
            "no_service_on_saturday",
            "no_service_on_sunday",
            "session_idle_timeout_minutes",
            "popelar_hours_per_day",
            "popelar_hourly_rate_czk",
        )
        labels = {
            "default_map_lat": "Výchozí zeměpisná šířka (lat)",
            "default_map_lng": "Výchozí zeměpisná délka (lng)",
            "waste_docs_default_range_days": "Počet dnů pro předvyplnění filtru jízd",
            "svoz_disable_yard_daily_submit_limit": (
                "Vypnout denní limit odeslání matice svozů ze sběrného dvora"
            ),
            "enforce_container_passport_move_check": (
                "Kontrolovat přistavení/stažení kontejneru podle pasportu"
            ),
            "customer_request_daily_cutoff_time": "Automatické uzavření požadavků (čas)",
            "no_service_on_saturday": "Sobota — nejezdíme",
            "no_service_on_sunday": "Neděle — nejezdíme",
            "session_idle_timeout_minutes": "Odhlásit po nečinnosti (minuty)",
            "popelar_hours_per_day": "Hodiny za den Popelář",
            "popelar_hourly_rate_czk": "Sazba Popelář (Kč/h)",
        }
        widgets = {
            "customer_request_daily_cutoff_time": forms.TimeInput(
                format="%H:%M",
                attrs={"type": "time"},
            ),
            "session_idle_timeout_minutes": forms.NumberInput(attrs={"min": "5", "max": "480", "step": "1"}),
            "popelar_hours_per_day": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "popelar_hourly_rate_czk": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
        }

    def clean_waste_docs_default_range_days(self):
        days = self.cleaned_data.get("waste_docs_default_range_days")
        if days is None:
            return 90
        if days < 1 or days > 365:
            raise forms.ValidationError("Zadejte hodnotu v rozsahu 1 až 365 dnů.")
        return days

    def clean_session_idle_timeout_minutes(self):
        minutes = self.cleaned_data.get("session_idle_timeout_minutes")
        if minutes is None:
            return 30
        if minutes < 5 or minutes > 480:
            raise forms.ValidationError("Zadejte hodnotu v rozsahu 5 až 480 minut.")
        return minutes

    def clean_popelar_hours_per_day(self):
        value = self.cleaned_data.get("popelar_hours_per_day")
        if value is None:
            return value
        if value < 0 or value > 24:
            raise forms.ValidationError("Zadejte hodnotu v rozsahu 0 až 24 hodin.")
        return value

    def clean_popelar_hourly_rate_czk(self):
        value = self.cleaned_data.get("popelar_hourly_rate_czk")
        if value is None:
            return value
        if value < 0:
            raise forms.ValidationError("Sazba nesmí být záporná.")
        return value

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        stored_nav = None
        stored_perm = None
        if getattr(self.instance, "pk", None):
            stored_nav = self.instance.role_nav_defaults
            stored_perm = self.instance.role_permission_defaults
        nav_matrix = merged_role_nav_matrix(stored_nav if isinstance(stored_nav, dict) else None)
        perm_matrix = merged_role_permission_matrix(
            stored_perm if isinstance(stored_perm, dict) else None
        )
        for ri, (role, _) in enumerate(ROLE_CHOICES):
            for key in ROLE_NAV_FLAG_KEYS:
                fn = f"role_nav_{ri}_{key}"
                self.fields[fn] = forms.BooleanField(
                    label=f"{role} — {ROLE_NAV_LABELS_CZ[key]}",
                    required=False,
                    initial=nav_matrix[role][key],
                )
            for key in ROLE_PERMISSION_FLAG_KEYS:
                fn = f"role_perm_{ri}_{key}"
                self.fields[fn] = forms.BooleanField(
                    label=f"{role} — {ROLE_PERMISSION_LABELS_CZ[key]}",
                    required=False,
                    initial=perm_matrix[role][key],
                )

    def save(self, commit=True):
        instance = super().save(commit=False)
        nav_out: dict[str, dict[str, bool]] = {}
        perm_out: dict[str, dict[str, bool]] = {}
        for ri, (role, _) in enumerate(ROLE_CHOICES):
            nav_row: dict[str, bool] = {}
            perm_row: dict[str, bool] = {}
            for key in ROLE_NAV_FLAG_KEYS:
                fn = f"role_nav_{ri}_{key}"
                nav_row[key] = bool(self.cleaned_data.get(fn))
            for key in ROLE_PERMISSION_FLAG_KEYS:
                fn = f"role_perm_{ri}_{key}"
                perm_row[key] = bool(self.cleaned_data.get(fn))
            nav_out[role] = nav_row
            perm_out[role] = perm_row
        instance.role_nav_defaults = nav_out
        instance.role_permission_defaults = perm_out
        if commit:
            instance.save()
        return instance

    @property
    def role_nav_table(self):
        rows = []
        for ri, (role, _) in enumerate(ROLE_CHOICES):
            rows.append(
                {
                    "role": role,
                    "cells": [(key, self[f"role_nav_{ri}_{key}"]) for key in ROLE_NAV_FLAG_KEYS],
                }
            )
        return rows

    @property
    def role_nav_header(self):
        return [(key, ROLE_NAV_LABELS_CZ[key]) for key in ROLE_NAV_FLAG_KEYS]

    @property
    def role_permission_table(self):
        rows = []
        for ri, (role, _) in enumerate(ROLE_CHOICES):
            rows.append(
                {
                    "role": role,
                    "cells": [
                        (key, self[f"role_perm_{ri}_{key}"]) for key in ROLE_PERMISSION_FLAG_KEYS
                    ],
                }
            )
        return rows

    @property
    def role_permission_header(self):
        return [(key, ROLE_PERMISSION_LABELS_CZ[key]) for key in ROLE_PERMISSION_FLAG_KEYS]
