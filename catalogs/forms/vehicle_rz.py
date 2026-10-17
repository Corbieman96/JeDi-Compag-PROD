from django import forms

from catalogs.models import VehicleKindCatalog, VehicleRzCatalog, VehicleRzProfile
from catalogs.services.vehicle_kind_display import bind_vehicle_kind_select_labels
from catalogs.services.vehicle_kind_tree import would_create_parent_cycle


class VehicleKindCatalogForm(forms.ModelForm):
    """Číselník druhu vozidla — název, zkratka a nadřazený druh (strom síly vozidel)."""

    class Meta:
        model = VehicleKindCatalog
        fields = ("name", "shortcut", "parent_kind")
        labels = {
            "name": "Název druhu",
            "shortcut": "Zkratka",
            "parent_kind": "Nadřazený druh",
        }
        help_texts = {
            "parent_kind": (
                "Volitelně — např. 3H pod H. Potomek je silnější vozidlo: může obsloužit úkoly "
                "rodiče, ne naopak. Které druhy smí konkrétní odpad nastavíte u subjektu (F/P)."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = VehicleKindCatalog.objects.order_by("sort_order", "name", "pk")
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["parent_kind"].queryset = qs
        self.fields["parent_kind"].required = False
        bind_vehicle_kind_select_labels(self, "parent_kind")

    def clean_parent_kind(self):
        parent = self.cleaned_data.get("parent_kind")
        if not parent:
            return parent
        kind_id = self.instance.pk if self.instance and self.instance.pk else 0
        if kind_id and would_create_parent_cycle(int(kind_id), int(parent.pk)):
            raise forms.ValidationError("Výběr by vytvořil cyklus ve stromu druhů vozidel.")
        return parent

    def save(self, commit=True):
        from catalogs.services.vehicle_kind_compatibility import clear_vehicle_kind_compatibility_cache

        obj = super().save(commit=commit)
        if commit:
            clear_vehicle_kind_compatibility_cache()
        return obj


class VehicleRzProfileForm(forms.ModelForm):
    rz_value = forms.CharField(label="RZ vozidla", max_length=20)

    class Meta:
        model = VehicleRzProfile
        fields = ("vehicle_type", "has_trailer", "has_crane", "vehicle_kinds")
        labels = {
            "vehicle_type": "Poznámka",
            "has_trailer": "Možnost vleku",
            "has_crane": "Možnost ruky",
            "vehicle_kinds": "Druhy vozidla",
        }
        widgets = {
            "vehicle_kinds": forms.SelectMultiple(attrs={"size": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle_kinds"].queryset = VehicleKindCatalog.objects.order_by("sort_order", "name")
        bind_vehicle_kind_select_labels(self, "vehicle_kinds")
        if self.instance and self.instance.pk:
            self.fields["rz_value"].initial = self.instance.rz.value

    def save(self, commit=True):
        rz_value = (self.cleaned_data.get("rz_value") or "").strip().upper()
        profile = super().save(commit=False)
        if self.instance and self.instance.pk:
            rz = self.instance.rz
            rz.value = rz_value
            rz.save(update_fields=["value"])
        else:
            rz, _ = VehicleRzCatalog.objects.get_or_create(value=rz_value)
            profile.rz = rz
        if commit:
            profile.save()
            self.save_m2m()
        return profile
