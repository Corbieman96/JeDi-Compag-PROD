from django import forms

from catalogs.models import VehicleRzRepair


class VehicleRzRepairForm(forms.ModelForm):
    class Meta:
        model = VehicleRzRepair
        fields = ("repair_date", "hours", "note")
        widgets = {
            "repair_date": forms.DateInput(attrs={"type": "date"}),
            "hours": forms.NumberInput(attrs={"step": "0.25", "min": "0"}),
            "note": forms.TextInput(attrs={"maxlength": "500", "placeholder": "Popis opravy"}),
        }

    def clean_hours(self):
        value = self.cleaned_data.get("hours")
        if value is None:
            raise forms.ValidationError("Zadejte počet hodin.")
        if value < 0:
            raise forms.ValidationError("Hodiny nesmí být záporné.")
        return value
