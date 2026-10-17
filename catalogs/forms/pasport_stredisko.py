"""Formulář střediska pasportů."""

from __future__ import annotations

from django import forms

from catalogs.models import PasportStredisko


class PasportStrediskoForm(forms.ModelForm):
    class Meta:
        model = PasportStredisko
        fields = ("code", "name", "sort_order", "is_active")
        labels = {
            "code": "Kód střediska",
            "name": "Název",
            "sort_order": "Pořadí",
            "is_active": "Aktivní",
        }

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()
