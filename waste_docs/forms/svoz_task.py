from django import forms

from catalogs.models import DriverProfile
from waste_docs.models import SvozTask


class SvozTaskQuickEditForm(forms.ModelForm):
    class Meta:
        model = SvozTask
        fields = (
            "target_date",
            "assigned_driver",
            "container_numbers",
            "matrix_display_label",
            "yard_contact_note",
        )
        labels = {
            "target_date": "Datum požadavku (přeplánování)",
            "assigned_driver": "Přiřazený řidič",
            "container_numbers": "Čísla kontejnerů",
            "matrix_display_label": "Název řádku (zobrazení)",
            "yard_contact_note": "Poznámka ze dvora",
        }
        widgets = {
            "target_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_driver"].queryset = DriverProfile.objects.order_by(
            "last_name", "first_name", "personal_number"
        )
        self.fields["assigned_driver"].required = False
        self.fields["assigned_driver"].empty_label = "— nepřiřazeno —"
