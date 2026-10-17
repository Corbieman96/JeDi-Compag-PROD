"""Formulář hromadné výměny řidiče / RZ."""

from __future__ import annotations

from django import forms


class RideReassignDriverForm(forms.Form):
    drive_date = forms.DateField(input_formats=["%Y-%m-%d"])
    from_vehicle_rz_id = forms.IntegerField(min_value=0)
    from_driver_id = forms.IntegerField(min_value=0)
    new_driver_id = forms.IntegerField(min_value=1)
    new_vehicle_rz_id = forms.IntegerField(required=False, min_value=1)
    ride_pks = forms.CharField(
        help_text="Čárkou oddělená PK jízd, nebo více polí ride_pks.",
        required=False,
    )

    def clean_from_vehicle_rz_id(self):
        val = self.cleaned_data["from_vehicle_rz_id"]
        return int(val) or None

    def clean_from_driver_id(self):
        val = self.cleaned_data["from_driver_id"]
        return int(val) or None

    def clean_new_vehicle_rz_id(self):
        val = self.cleaned_data.get("new_vehicle_rz_id")
        if val in (None, "", 0):
            return None
        return int(val)

    def selected_ride_pks(self) -> list[int]:
        raw_list = self.data.getlist("ride_pks") if hasattr(self.data, "getlist") else []
        parts: list[str] = []
        if raw_list:
            for chunk in raw_list:
                parts.extend(str(chunk).split(","))
        else:
            parts.extend(str(self.cleaned_data.get("ride_pks") or "").split(","))
        out: list[int] = []
        seen: set[int] = set()
        for part in parts:
            part = (part or "").strip()
            if not part:
                continue
            try:
                pk = int(part)
            except (TypeError, ValueError):
                continue
            if pk not in seen:
                seen.add(pk)
                out.append(pk)
        return out
