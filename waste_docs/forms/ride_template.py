from django import forms

from catalogs.models import VehicleKindCatalog
from waste_docs.models import RideTemplate


class RideTemplateForm(forms.ModelForm):
    class Meta:
        model = RideTemplate
        fields = (
            "title",
            "activity",
            "applicable_vehicle_kinds",
            "name",
            "ico",
            "address",
            "waste_type",
            "suffix",
            "vehicle_rz",
            "driver",
            "container_number",
            "container_number_2",
            "contact_phone",
            "contract_number",
            "contact_note",
        )
        labels = {
            "title": "Název šablony",
            "activity": "Činnost",
            "applicable_vehicle_kinds": "Platí pro druhy vozidel",
            "name": "Název F/P osoby",
            "ico": "IČO",
            "address": "Adresa plnění",
            "waste_type": "Název druhu odpadu",
            "suffix": "Koncovka",
            "vehicle_rz": "RZ vozidla",
            "driver": "Řidič",
            "container_number": "Číslo kontejneru (1)",
            "container_number_2": "Číslo kontejneru (2)",
            "contact_phone": "Telefon",
            "contract_number": "Číslo smlouvy",
            "contact_note": "Poznámka",
        }
        widgets = {
            "applicable_vehicle_kinds": forms.CheckboxSelectMultiple(
                attrs={"class": "checkbox-multiple-stack"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["applicable_vehicle_kinds"].queryset = VehicleKindCatalog.objects.order_by(
            "sort_order", "name"
        )
        self.fields["applicable_vehicle_kinds"].required = True

    def clean(self):
        data = super().clean()
        kinds = data.get("applicable_vehicle_kinds")
        if not kinds:
            self.add_error(
                "applicable_vehicle_kinds",
                "Vyberte alespoň jeden druh vozidla (šablona se podle toho nabízí u nové jízdy).",
            )
        return data

    def save(self, commit=True):
        obj = super().save(commit=False)
        kinds = list(self.cleaned_data.get("applicable_vehicle_kinds") or [])
        if kinds:
            primary = min(kinds, key=lambda k: (k.sort_order, (k.name or "").lower(), k.pk))
            obj.vehicle_kind = primary
        if commit:
            obj.save()
            self.save_m2m()
        return obj
