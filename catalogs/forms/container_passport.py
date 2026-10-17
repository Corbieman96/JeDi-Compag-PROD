"""Formuláře pasportu kontejneru."""

from __future__ import annotations

import os

from django import forms
from django.core.exceptions import ValidationError

from catalogs.models import ContainerPassport

_ALLOWED_IMAGE_EXT = frozenset({".jpg", ".jpeg", ".png", ".webp"})
_MAX_PHOTO_BYTES = 8 * 1024 * 1024


def _clean_image(f, field_label: str):
    if not f:
        raise ValidationError(f"{field_label}: vyberte soubor.")
    name = getattr(f, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in _ALLOWED_IMAGE_EXT:
        raise ValidationError(f"{field_label}: povolené formáty JPEG, PNG, WebP.")
    if hasattr(f, "size") and f.size > _MAX_PHOTO_BYTES:
        raise ValidationError(f"{field_label}: soubor je větší než 8 MB.")
    return f


class ContainerPassportForm(forms.ModelForm):
    class Meta:
        model = ContainerPassport
        fields = (
            "container_number",
            "vehicle_kind",
            "stredisko",
            "volume_m3",
            "container_size_ft",
            "vehicle_requirement_note",
            "color",
            "year_manufactured",
            "photo_1",
            "photo_2",
            "photo_3",
            "notes",
        )
        labels = {
            "container_number": "Číslo kontejneru",
            "vehicle_kind": "Druh vozidla",
            "stredisko": "Středisko",
            "volume_m3": "Objem (m³)",
            "container_size_ft": "Velikost (′)",
            "vehicle_requirement_note": "Požadavek na vozidlo",
            "color": "Barva",
            "year_manufactured": "Rok výroby",
            "photo_1": "Fotografie 1",
            "photo_2": "Fotografie 2",
            "photo_3": "Fotografie 3",
            "notes": "Poznámka",
        }

    def __init__(self, *args, **kwargs):
        from catalogs.services.vehicle_kind_display import bind_vehicle_kind_select_labels

        super().__init__(*args, **kwargs)
        self.fields["vehicle_kind"].queryset = self.fields["vehicle_kind"].queryset.order_by(
            "sort_order", "name", "pk"
        )
        bind_vehicle_kind_select_labels(self, "vehicle_kind")
        self.fields["year_manufactured"].required = False
        self.fields["notes"].required = False
        self.fields["stredisko"].required = False
        self.fields["container_size_ft"].required = False
        self.fields["volume_m3"].required = False
        self.fields["vehicle_requirement_note"].required = False
        self.fields["stredisko"].queryset = (
            self.fields["stredisko"].queryset.filter(is_active=True).order_by("sort_order", "code", "pk")
        )
        self.fields["photo_1"].required = False
        self.fields["photo_2"].required = False
        self.fields["photo_3"].required = False

    def clean_photo_1(self):
        f = self.cleaned_data.get("photo_1")
        if f is False:
            f = None
        if not f and self.instance and self.instance.pk and self.instance.photo_1:
            return self.instance.photo_1
        if not f:
            return None
        return _clean_image(f, "Fotografie 1")

    def clean_photo_2(self):
        f = self.cleaned_data.get("photo_2")
        if f is False:
            f = None
        if not f and self.instance and self.instance.pk and self.instance.photo_2:
            return self.instance.photo_2
        if not f:
            return None
        return _clean_image(f, "Fotografie 2")

    def clean_photo_3(self):
        f = self.cleaned_data.get("photo_3")
        if f is False:
            f = None
        if not f and self.instance and self.instance.pk and self.instance.photo_3:
            return self.instance.photo_3
        if not f:
            return None
        return _clean_image(f, "Fotografie 3")
