from django import forms

from catalogs.models import DriverAbsence, DriverProfile


class DriverAbsenceForm(forms.ModelForm):
    class Meta:
        model = DriverAbsence
        fields = ("absence_type", "date_from", "date_to", "is_partial", "note")
        widgets = {
            "absence_type": forms.Select(),
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
            "is_partial": forms.CheckboxInput(),
            "note": forms.Textarea(attrs={"rows": 3}),
        }


class DriverAbsenceQuickForm(forms.ModelForm):
    """Rychlé zadání nepřítomnosti z dashboardu (řidič je v hidden podle řádku)."""

    class Meta:
        model = DriverAbsence
        fields = ("driver", "absence_type", "date_from", "date_to", "is_partial", "note")
        widgets = {
            "driver": forms.HiddenInput(),
            "absence_type": forms.Select(attrs={"class": "dash-absence-type"}),
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
            "is_partial": forms.CheckboxInput(),
            "note": forms.Textarea(attrs={"rows": 2, "class": "dash-absence-note"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = DriverProfile.objects.all()
